# Unified Development Plan: External CasCor Dashboard Integration

- **Version**: 1.0.0
- **Date**: 2026-03-26
- **Author**: Amp (AI Agent)
- **Status**: Ready for Implementation
- **Supersedes**: `CANOPY_EXTERNAL_CASCOR_PLAN.md` (v1.0.0), `EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md` (v2.0.0), `DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md` (v1.0.0)
- **Source Analysis**: Synthesized from three analysis documents and two prior development plans, cross-validated by five independent review agents against the current codebase.

---

## 1. Executive Summary

When juniper-canopy connects to an externally running juniper-cascor instance,
the dashboard displays no training data — no metrics, no status updates, no
topology changes. Codebase analysis across three repositories identified
**one systemic root cause** producing **8 distinct integration failures** plus
**3 additional issues** found during plan validation.

**Systemic root cause**: The `_ServiceTrainingMonitor` and `CascorStateSync`
classes were developed against `FakeCascorClient`, whose response format
structurally diverges from the real cascor server's `ResponseEnvelope`. Every
method that reads response fields uses the fake client's key layout, which
does not match the real server.

**Fix strategy**: Add a **single normalization boundary** in
`CascorServiceAdapter` — built on the existing `_unwrap_response()` method —
that translates cascor's native API responses into the canonical shapes the
dashboard already consumes. This avoids breaking changes to the client library
and centralizes all format translation in one place.

**Estimated effort**: 6–10 hours across 6 phases
**Repos modified**: juniper-canopy (primary), juniper-cascor-client (fake
client only)
**Repos unmodified**: juniper-cascor (no server changes required)

---

## 2. Problem Statement

The juniper-canopy dashboard has two backends: `DemoBackend` (local simulation)
and `ServiceBackend` (connects to real cascor via REST/WebSocket). The demo
backend works correctly. The service backend connects and attaches successfully,
but every data path from cascor to the dashboard is broken:

| Dashboard Element               | Expected           | Actual           | Root Cause                            |
|---------------------------------|--------------------|------------------|---------------------------------------|
| Metrics charts (loss, accuracy) | Live curves        | Empty            | FIX-1: wrong envelope key             |
| Status bar (Running/Paused)     | FSM state          | Always "Stopped" | FIX-4: wrong response shape           |
| Epoch counter                   | Current epoch      | Always 0         | FIX-4: nested structure not flattened |
| Hidden units counter            | Unit count         | Always 0         | FIX-4: nested structure not flattened |
| Phase indicator                 | Output/Candidate   | Always "Idle"    | FIX-4: nested structure not flattened |
| Initial state on connect        | Synced from cascor | Defaults         | FIX-5: sync reads wrong keys          |
| `is_training` flag              | True when active   | Always False     | FIX-2: wrong envelope level           |
| Current metrics snapshot        | Metric values      | Envelope wrapper | FIX-3: no unwrapping                  |

---

## 3. Root Cause Chain

All failures trace to a single systemic issue:

```bash
FIX-SYS: FakeCascorClient response format diverges from real cascor ResponseEnvelope
  │
  ├── FIX-1 (CRITICAL): _ServiceTrainingMonitor.get_recent_metrics() → always []
  │     result.get("history", []) but real response has {"data": [...]}
  │
  ├── FIX-2 (MODERATE): _ServiceTrainingMonitor.is_training → always False
  │     status.get("is_training", False) but real response nests at data.training_active
  │
  ├── FIX-3 (MODERATE): _ServiceTrainingMonitor.get_current_metrics() → full envelope
  │     Returns raw client response without unwrapping
  │
  ├── FIX-4 (CRITICAL): ServiceBackend.get_status() → wrong response shape
  │     Returns nested cascor structure; dashboard expects flat keys
  │
  └── FIX-5 (CRITICAL): CascorStateSync.sync() → wrong initial state
        Reads data.state, data.epoch — real has data.state_machine, data.monitor
```

**Why `_ServiceTrainingMonitor` is particularly affected**: It wraps the raw
`JuniperCascorClient` directly and does **not** call
`CascorServiceAdapter._unwrap_response()`. The adapter's other methods (e.g.,
`get_training_status()`, `get_network_data()`) do unwrap correctly, but the
monitor class bypasses this entirely.

---

## 4. Response Format Divergence Reference

### 4.1 Training Status

| Aspect        | FakeCascorClient                | Real CasCor Server                                 |
|---------------|---------------------------------|----------------------------------------------------|
| Status field  | `"status": "ok"`                | `"status": "success"`                              |
| Training flag | Top-level `"is_training": bool` | `data.training_active: bool`                       |
| State string  | `data.state: "training"`        | `data.state_machine.status: "STARTED"` (uppercase) |
| Phase string  | `data.phase: "output"`          | `data.state_machine.phase: "OUTPUT"` (uppercase)   |
| Epoch         | `data.epoch: int`               | `data.monitor.current_epoch: int`                  |
| Max epochs    | `data.max_epochs: int`          | `data.training_state.max_epochs: int`              |
| Meta field    | Absent                          | `"meta": {"timestamp": float, "version": str}`     |

### 4.2 Metrics History

| Aspect             | FakeCascorClient                                           | Real CasCor Server                                           |
|--------------------|------------------------------------------------------------|--------------------------------------------------------------|
| Data shape         | `data: {"history": [...], "total": N}`                     | `data: [...]` (bare list)                                    |
| Metric field names | `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy` | `loss`, `accuracy`, `validation_loss`, `validation_accuracy` |
| Meta field         | Absent                                                     | Present                                                      |

### 4.3 Current Metrics

| Aspect             | FakeCascorClient               | Real CasCor Server                    |
|--------------------|--------------------------------|---------------------------------------|
| Metric field names | `train_loss`, `train_accuracy` | `train_loss`, `train_accuracy` (same) |
| Extra fields       | `correlation`, `phase`         | `timestamp`                           |
| Meta field         | Absent                         | Present                               |

> **Note**: The current metrics snapshot (`get_metrics()`) already uses
> canopy-compatible field names (`train_loss`, `train_accuracy`). Only the
> **history entries** from `TrainingMonitor` use the raw names (`loss`,
> `accuracy`, `validation_loss`, `validation_accuracy`).

### 4.4 Training Params

| Aspect     | FakeCascorClient                         | Real CasCor Server                           |
|------------|------------------------------------------|----------------------------------------------|
| Data shape | `data: {"params": {...}, "epochs": int}` | `data: {"learning_rate": float, ...}` (flat) |
| Meta field | Absent                                   | Present                                      |

---

## 5. Previously Identified Gaps — Current Status

Cross-referencing the original `CANOPY_EXTERNAL_CASCOR_PLAN.md` gaps against
the current codebase:

| Gap   | Original Description                  | Current Status                                                                                       | Action                                |
|-------|---------------------------------------|------------------------------------------------------------------------------------------------------|---------------------------------------|
| Gap 1 | Backend factory ignores settings      | **Resolved** — `create_backend()` reads settings; env vars are legacy fallback                       | None                                  |
| Gap 2 | State not hydrated on connect         | **Partially resolved** — `initialize()` calls `sync()` at line 142, but sync reads wrong fields      | FIX-5                                 |
| Gap 3 | `/api/state` defaults in service mode | **Resolved** — `main.py:583-615` fetches live params via `get_canopy_params()`                       | Verify envelope handling (FIX-10)     |
| Gap 4 | Discovery env var mutation            | **Resolved** — lifespan passes URL directly to `create_backend()`                                    | None                                  |
| Gap 5 | Parameter mapping incomplete          | **Resolved** — both maps have 7 entries                                                              | Fix reverse map inconsistency (FIX-9) |
| Gap 6 | No topology refresh on cascade events | **Resolved** — relay loop handles `cascade_add`                                                      | None                                  |
| Gap 7 | Response normalization inconsistent   | **Open** — `_ServiceTrainingMonitor` bypasses `_unwrap_response()`                                   | FIX-1, FIX-2, FIX-3                   |
| Gap 8 | Local training_state drifts           | **Resolved** — relay calls `_state_update_callback` (lines 189-206)                                  | None                                  |
| Gap 9 | Auth env var miswired                 | **Resolved** — `create_backend()` uses `JUNIPER_CASCOR_API_KEY` with `JUNIPER_DATA_API_KEY` fallback | None                                  |

---

## 6. Canonical Internal Contract

After normalization, all code within canopy sees these canonical shapes.
Both `DemoBackend` and `ServiceBackend` must produce identical structures.

### 6.1 Status Contract (`get_status()` return value)

```python
{
    "is_training": bool,         # Overall training active flag
    "is_running": bool,          # True when actively training
    "is_paused": bool,           # True when paused
    "completed": bool,           # True when training finished
    "failed": bool,              # True when training errored
    "fsm_status": str,           # Raw FSM status string (title case)
    "phase": str,                # "idle" | "output" | "candidate" | "inference"
    "current_epoch": int,        # Current training epoch (0 is valid)
    "hidden_units": int,         # Current cascade hidden unit count (0 is valid)
    "network_connected": bool,   # Backend connection status
    "monitoring_active": bool,   # Monitoring active flag
}
```

### 6.2 Metrics History Contract (`get_metrics_history()` return value)

```python
[
    {
        "epoch": int,
        "train_loss": float | None,
        "train_accuracy": float | None,
        "val_loss": float | None,
        "val_accuracy": float | None,
        "hidden_units": int,
        "phase": str | None,
        "timestamp": float | None,
    },
    ...
]
```

> **REST endpoint contract**: The `/api/metrics/history` endpoint
> (`main.py:640-650`) wraps this list in `{"history": backend.get_metrics_history(count)}`.
> The dashboard handler (`dashboard_manager.py:1694-1701`) reads
> `payload["history"]` to populate metrics stores. The handler is resilient
> and accepts `{"history": [...]}`, `{"data": [...]}`, or a bare list —
> but the canonical REST response shape is `{"history": [...]}`.

### 6.3 State Contract (`/api/state` return value)

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
    "current_epoch": int,
    "learning_rate": float,
    "max_hidden_units": int,
    "max_epochs": int,
}
```

### 6.4 Dataset Contract (`get_dataset()` return value)

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

### 6.5 Value Preservation Rules

- **`0` and `0.0` are valid values** — never treat as missing. Use
  `is not None` checks, never `or` chains, for numeric fields.
- **`False` is a valid value** — never let it fall through in boolean
  detection. Use explicit `is not None` checks.
- **Enum values are normalized to lowercase** for `phase` fields and
  title case for `status` fields at the normalization boundary.

---

## 7. Fix Strategy

### Architecture: Single Normalization Boundary

All external cascor payload translation happens at **one boundary** built on
the existing `_unwrap_response()` method. After this boundary, the rest of the
codebase sees one canonical internal shape.

```bash
juniper-cascor (REST API)
  │ ResponseEnvelope: {"status":"success","data":...,"meta":...}
  ▼
juniper-cascor-client (JuniperCascorClient)
  │ Returns raw response.json() — no unwrapping (unchanged)
  ▼
CascorServiceAdapter  ─── NORMALIZATION BOUNDARY ───
  │ _unwrap_response()       → strips envelope (existing)
  │ _first_defined()         → handles falsy-but-valid values (new)
  │ _is_cascor_nested()      → detects real vs fake response shape (new)
  │ _normalize_status()      → flat dict matching DemoBackend (new)
  │ _normalize_metric()      → canonical metric field names (new)
  │ _normalize_case()        → UPPERCASE → lowercase/title case (new)
  ▼
ServiceBackend / _ServiceTrainingMonitor / CascorStateSync
  │ Consume normalized data (same shape as DemoBackend)
  ▼
main.py REST endpoints → Dashboard callbacks
  │ Dashboard reads flat keys: is_running, phase, train_loss, etc.
  ▼
Dashboard renders correctly
```

### Why Not Fix at Client Library Level?

- Breaking API change for `JuniperCascorClient` — all consumers affected
- The client should remain a thin transport mirror of the real service
- Normalization is a UI-layer concern, not a transport concern
- Lower risk; ships without cross-repo coordination

---

## 8. Consolidated Fix Registry

Every distinct issue requiring a code change, deduplicated and sequenced:

| ID      | Severity      | File                                | Description                                                                                                                                                                | Phase |
|---------|---------------|-------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| FIX-1   | **CRITICAL**  | `cascor_service_adapter.py:74-77`   | `get_recent_metrics()` uses `result.get("history", [])` — must unwrap envelope and handle both list and dict formats                                                       | 2     |
| FIX-2   | **CRITICAL**  | `cascor_service_adapter.py:60-66`   | `is_training` reads top-level `is_training` — must unwrap and check `data.training_active` using `is not None` guard                                                       | 2     |
| FIX-3   | **MODERATE**  | `cascor_service_adapter.py:68-72`   | `get_current_metrics()` returns raw client response — must unwrap envelope                                                                                                 | 2     |
| FIX-4   | **CRITICAL**  | `service_backend.py:100-101`        | `get_status()` returns nested cascor structure — must transform to flat dashboard format with `_first_defined()` for falsy values                                          | 2     |
| FIX-5   | **CRITICAL**  | `state_sync.py:57-65`               | `sync()` reads wrong keys; also never populates `SyncedState.phase`                                                                                                        | 3     |
| FIX-6   | **CRITICAL**  | `state_sync.py:88-95`               | `sync()` metrics history: `data.history` vs bare list                                                                                                                      | 3     |
| FIX-7   | **CRITICAL**  | `state_sync.py:70-75`               | `sync()` params: `data.params` vs flat `data`                                                                                                                              | 3     |
| FIX-8   | **MODERATE**  | `cascor_service_adapter.py:281-286` | `is_training_in_progress()` has same envelope bug as FIX-2. Used by `ServiceBackend.is_training_active()` and as guard in `start_training()`                               | 2     |
| FIX-9   | **IMPORTANT** | `cascor_service_adapter.py:332-340` | Reverse param map asymmetry: `patience` → `cn_training_convergence_threshold` should be `nn_growth_convergence_threshold`. Fix by auto-generating reverse from forward map | 4     |
| FIX-10  | **IMPORTANT** | `cascor_service_adapter.py:359-375` | `get_canopy_params()` dual-path logic needs harmonization: ensure both paths return identical canonical param names                                                        | 4     |
| FIX-11  | **IMPORTANT** | `service_backend.py`                | Dataset response key mapping: cascor `train_samples` → `num_samples`, `input_features` → `num_features`                                                                    | 4     |
| FIX-12  | **MODERATE**  | `state_sync.py:100-116`             | Status normalization missing uppercase entries: `"STARTED"` → `"Started"`, `"PAUSED"` → `"Paused"`, etc.                                                                   | 3     |
| FIX-13  | **MODERATE**  | `cascor_service_adapter.py`         | History metric field names: `loss` → `train_loss`, `accuracy` → `train_accuracy`, `validation_loss` → `val_loss`, `validation_accuracy` → `val_accuracy`                   | 1     |
| FIX-14  | **MODERATE**  | `service_backend.py`                | Topology format verification: compare cascor shape against `network_visualizer.py` expectations                                                                            | 4     |
| FIX-SYS | **SYSTEMIC**  | `fake_client.py` (cascor-client)    | `FakeCascorClient` response format must match real server `ResponseEnvelope`                                                                                               | 5     |

**FIX crosswalk**: This registry consolidates items from the prior
`EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md` (EXT) and
`DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md` (DEV). Mapping:

| Unified | EXT Source | DEV Source         | Notes                                    |
|---------|------------|--------------------|------------------------------------------|
| FIX-1   | EXT FIX-1  | DEV RC-1           |                                          |
| FIX-2   | EXT FIX-2  | DEV RC-2           |                                          |
| FIX-3   | EXT FIX-3  | DEV RC-3           |                                          |
| FIX-4   | EXT FIX-4  | DEV ISS-1          |                                          |
| FIX-5   | EXT FIX-5  | DEV RC-4           |                                          |
| FIX-6   | EXT FIX-6  | DEV RC-4           | Metrics history subset                   |
| FIX-7   | EXT FIX-7  | DEV RC-4           | Params subset                            |
| FIX-8   | EXT FIX-14 | DEV RC-2 (partial) | `is_training_in_progress()`              |
| FIX-9   | EXT FIX-9  | DEV ISS-2          | Param map asymmetry                      |
| FIX-10  | —          | —                  | New: `get_canopy_params()` harmonization |
| FIX-11  | EXT FIX-10 | DEV ISS-4          | Dataset key mapping                      |
| FIX-12  | EXT FIX-13 | —                  | Status normalization case                |
| FIX-13  | —          | DEV ISS-3          | Metric field name normalization          |
| FIX-14  | EXT FIX-15 | —                  | Topology format verification             |
| FIX-SYS | EXT FIX-12 | DEV RC-5           | FakeCascorClient alignment               |
| —       | EXT FIX-8  | —                  | Already implemented (`/api/state`)       |
| —       | EXT FIX-11 | —                  | Already implemented (relay callback)     |

**Items confirmed already implemented (no action needed):**

- `/api/state` service mode handling (`main.py:583-615`)
- Relay state callback wiring (`cascor_service_adapter.py:189-206`, `main.py:202`)
- Discovery URL passing (lifespan passes directly to `create_backend()`)
- Topology refresh on `cascade_add` (relay loop handles this)
- Backend factory settings usage (`create_backend()` reads `get_settings()`)

---

## 9. Phased Implementation Plan

### Phase 0: Characterization Tests

**Priority**: Prerequisite
**Scope**: juniper-canopy tests only
**Estimated time**: 45 min
**Depends on**: Nothing

Write characterization tests that capture the **current behavior** with real
cascor response formats. These tests initially **fail** (documenting the bugs),
then pass after production fixes are applied.

#### Changes

1. **`src/tests/fixtures/cascor_response_fixtures.py`** — **NEW**

   Reusable fixtures containing real cascor `ResponseEnvelope`-formatted
   responses. All fixtures must use **uppercase** enum values (`STARTED`,
   `OUTPUT`) matching the real server:

   - `real_training_status_active()` — nested `state_machine` (status=`STARTED`),
     `monitor` (current_epoch=42), `training_state`, `training_active=True`
   - `real_training_status_idle()` — `training_active=False`, epoch=0
   - `real_metrics_history()` — `data` as flat list with `loss`, `accuracy`
     field names (not `train_loss`)
   - `real_metrics_current()` — single metric in envelope
   - `real_training_params()` — flat param dict in envelope
   - `real_topology()` — weight-oriented format
   - `real_dataset()` — metadata-only format

2. **`src/tests/unit/test_response_normalization.py`** — **NEW**

   Test cases (expected to fail initially):

   | Test                                          | Validates                                         |
   |-----------------------------------------------|---------------------------------------------------|
   | `test_get_recent_metrics_with_real_envelope`  | FIX-1: `data: [list]` format returns metrics list |
   | `test_get_recent_metrics_with_fake_envelope`  | FIX-1: `data.history` format still works          |
   | `test_is_training_with_real_envelope`         | FIX-2: `data.training_active=True` → `True`       |
   | `test_is_training_false_not_fallthrough`      | FIX-2: `is_training=False` doesn't fall through   |
   | `test_get_current_metrics_unwraps`            | FIX-3: returns inner dict, not envelope           |
   | `test_get_status_normalizes_cascor`           | FIX-4: nested → flat transformation               |
   | `test_get_status_epoch_zero_preserved`        | FIX-4: epoch=0 not treated as missing             |
   | `test_get_status_hidden_units_zero_preserved` | FIX-4: hidden_units=0 preserved                   |
   | `test_get_status_uppercase_started`           | FIX-4: `STARTED` → `is_running=True`              |
   | `test_get_status_passthrough_flat`            | FIX-4: demo-format dict passes through            |
   | `test_state_sync_real_envelope`               | FIX-5: correct epoch, status, phase from nested   |
   | `test_metrics_history_field_normalization`    | FIX-13: `loss` → `train_loss`                     |
   | `test_is_training_in_progress_real`           | FIX-8: same fix as FIX-2                          |

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v
# Expected: tests FAIL (documenting current bugs)
```

---

### Phase 1: Shared Normalization Helpers

**Priority**: Critical — foundation for all subsequent fixes
**Scope**: `canopy/src/backend/cascor_service_adapter.py`
**Estimated time**: 30 min
**Depends on**: Phase 0

Add the shared helper methods that all subsequent fixes use. No behavior
changes yet — just adding the infrastructure.

#### Changes, Phase 1

1. **`src/backend/cascor_service_adapter.py`** — Add `_first_defined()`:

   ```python
   def _first_defined(*values, default=None):
       """Return the first value that is not None, or default.

       Unlike `or` chains, this correctly preserves falsy-but-valid values
       like 0, 0.0, False, and empty strings.
       """
       for v in values:
           if v is not None:
               return v
       return default
   ```

   This is a **module-level function** (not a method) so it can be imported
   by both `service_backend.py` and `state_sync.py`.

2. **`src/backend/cascor_service_adapter.py`** — Add `_is_cascor_nested()`:

   ```python
   @staticmethod
   def _is_cascor_nested(data: dict) -> bool:
       """Detect whether the data dict uses cascor's nested structure
       (state_machine/monitor/training_state) vs the flat demo format.

       Uses positive detection of nested structure rather than checking
       for flat keys, which could misfire if cascor ever adds a flat field.
       """
       return "state_machine" in data or "training_active" in data
   ```

3. **`src/backend/cascor_service_adapter.py`** — Add `_normalize_metric()`:

   ```python
   @staticmethod
   def _normalize_metric(entry: dict) -> dict:
       """Normalize a single metric entry to canopy's canonical field names.

       Handles both real cascor names (loss, accuracy, validation_loss,
       validation_accuracy) and canopy names (train_loss, train_accuracy,
       val_loss, val_accuracy). Uses _first_defined to preserve 0.0 values.
       """
       return {
           "epoch": entry.get("epoch", 0),
           "train_loss": _first_defined(
               entry.get("train_loss") if "train_loss" in entry else None,
               entry.get("loss") if "loss" in entry else None,
           ),
           "train_accuracy": _first_defined(
               entry.get("train_accuracy") if "train_accuracy" in entry else None,
               entry.get("accuracy") if "accuracy" in entry else None,
           ),
           "val_loss": _first_defined(
               entry.get("val_loss") if "val_loss" in entry else None,
               entry.get("validation_loss") if "validation_loss" in entry else None,
           ),
           "val_accuracy": _first_defined(
               entry.get("val_accuracy") if "val_accuracy" in entry else None,
               entry.get("validation_accuracy") if "validation_accuracy" in entry else None,
           ),
           "hidden_units": entry.get("hidden_units", 0),
           "phase": entry.get("phase"),
           "timestamp": entry.get("timestamp"),
       }
   ```

   > **Key design choice**: Uses `"key" in entry` checks instead of `or`
   > chains. This correctly handles `train_loss: 0.0` (a perfectly valid
   > metric value at convergence) without falling through to the `loss`
   > key.

4. **Reuse existing `_unwrap_response()`** — Do NOT create a new
   `_unwrap_envelope()`. The existing method at line 381-391 already handles
   envelope stripping correctly.

#### Verification, Phase 1

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
python -c "from backend.cascor_service_adapter import _first_defined; print(_first_defined(0, 1, default=99))"
# Expected: 0 (not 1 or 99)
```

---

### Phase 2: Read-Path Fixes (CRITICAL — Unblocks All Display)

**Priority**: Critical — blocks all dashboard data in service mode
**Scope**: `cascor_service_adapter.py`, `service_backend.py`
**Estimated time**: 2 hours
**Depends on**: Phase 1

Fix all methods in `_ServiceTrainingMonitor` and `ServiceBackend` that read
raw client responses without proper normalization. This fixes FIX-1, FIX-2,
FIX-3, FIX-4, FIX-8, and FIX-13.

#### 2.1 Fix `_ServiceTrainingMonitor` Methods

**File**: `canopy/src/backend/cascor_service_adapter.py`

**FIX-1: `get_recent_metrics()` (lines 74-77)**

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        if isinstance(result, dict):
            data = result.get("data", result)
            if isinstance(data, list):
                return [CascorServiceAdapter._normalize_metric(m) for m in data]
            if isinstance(data, dict):
                history = data.get("history", [])
                return [CascorServiceAdapter._normalize_metric(m) for m in history]
        return result if isinstance(result, list) else []
    except JuniperCascorClientError:
        return []
```

**FIX-2: `is_training` property (lines 60-66)**

```python
@property
def is_training(self) -> bool:
    try:
        status = self._client.get_training_status()
        # Check top-level first (FakeCascorClient), with explicit None guard
        # so that is_training=False doesn't fall through
        is_training_top = status.get("is_training")
        if is_training_top is not None:
            return is_training_top
        # Unwrap envelope and check nested (real server)
        data = status.get("data", {})
        if isinstance(data, dict):
            return data.get("training_active", False)
        return False
    except JuniperCascorClientError:
        return False
```

**FIX-3: `get_current_metrics()` (lines 68-72)**

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        result = self._client.get_metrics()
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            return CascorServiceAdapter._normalize_metric(data) if isinstance(data, dict) else result
        return result if isinstance(result, dict) else {}
    except JuniperCascorClientError:
        return {}
```

#### 2.2 Fix `CascorServiceAdapter.is_training_in_progress()` (FIX-8)

**File**: `canopy/src/backend/cascor_service_adapter.py` (lines 281-286)

Same logic as FIX-2 — both methods must use identical envelope handling:

```python
def is_training_in_progress(self) -> bool:
    try:
        status = self._client.get_training_status()
        is_training_top = status.get("is_training")
        if is_training_top is not None:
            return is_training_top
        data = status.get("data", {})
        if isinstance(data, dict):
            return data.get("training_active", False)
        return False
    except JuniperCascorClientError:
        return False
```

#### 2.3 Fix `ServiceBackend.get_status()` Response Shape (FIX-4)

**File**: `canopy/src/backend/service_backend.py` (lines 100-101)

Transform cascor's nested status into the flat dict the dashboard expects.
Uses `_first_defined()` for all numeric fields to preserve valid `0` values.
Uses `_is_cascor_nested()` for positive structure detection.

```python
from backend.cascor_service_adapter import _first_defined, CascorServiceAdapter

def get_status(self) -> Dict[str, Any]:
    raw = self._adapter.get_training_status()
    # raw is already unwrapped by _unwrap_response() in the adapter
    if not isinstance(raw, dict) or not CascorServiceAdapter._is_cascor_nested(raw):
        return raw  # Already flat (demo-compatible format)

    sm = raw.get("state_machine", {}) if isinstance(raw.get("state_machine"), dict) else {}
    monitor = raw.get("monitor", {}) if isinstance(raw.get("monitor"), dict) else {}
    ts = raw.get("training_state", {}) if isinstance(raw.get("training_state"), dict) else {}

    fsm_status = sm.get("status", sm.get("current_state", "Stopped"))
    status_upper = fsm_status.upper() if isinstance(fsm_status, str) else "STOPPED"

    return {
        "is_training": raw.get("training_active", False),
        "is_running": status_upper in ("STARTED", "RUNNING", "TRAINING"),
        "is_paused": status_upper == "PAUSED",
        "completed": status_upper in ("COMPLETED", "CONVERGED"),
        "failed": status_upper == "FAILED",
        "fsm_status": fsm_status,
        "phase": (sm.get("phase") or ts.get("phase", "idle")).lower()
            if isinstance(sm.get("phase") or ts.get("phase", "idle"), str) else "idle",
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
        "monitoring_active": status_upper in ("STARTED", "RUNNING", "TRAINING"),
        "input_size": ts.get("input_size", 0),
        "output_size": ts.get("output_size", 0),
        "learning_rate": ts.get("learning_rate", 0.0),
        "max_hidden_units": ts.get("max_hidden_units", 0),
        "max_epochs": ts.get("max_epochs", 0),
    }
```

#### Dashboard Key Mapping Reference

| Dashboard Key       | Cascor Source Path                    | DemoBackend Equivalent            |
|---------------------|---------------------------------------|-----------------------------------|
| `is_running`        | `state_machine.status == "STARTED"`   | `self._fsm.status == "STARTED"`   |
| `is_paused`         | `state_machine.status == "PAUSED"`    | `self._fsm.status == "PAUSED"`    |
| `completed`         | `state_machine.status == "COMPLETED"` | `self._fsm.status == "COMPLETED"` |
| `failed`            | `state_machine.status == "FAILED"`    | `self._fsm.status == "FAILED"`    |
| `phase`             | `state_machine.phase` (lowercased)    | `self._training_phase`            |
| `current_epoch`     | `monitor.current_epoch`               | `self._current_epoch`             |
| `hidden_units`      | `monitor.current_hidden_units`        | `self._hidden_units`              |
| `is_training`       | `training_active`                     | `self._is_training`               |
| `network_connected` | `network_loaded`                      | `self._network is not None`       |

#### Tests for Phase 2

| Test                                     | File                             | Validates                                                          |
|------------------------------------------|----------------------------------|--------------------------------------------------------------------|
| `test_get_recent_metrics_real_envelope`  | `test_response_normalization.py` | FIX-1                                                              |
| `test_get_recent_metrics_fake_envelope`  | `test_response_normalization.py` | FIX-1 compat                                                       |
| `test_get_recent_metrics_empty_data`     | `test_response_normalization.py` | FIX-1 edge                                                         |
| `test_is_training_real_envelope`         | `test_response_normalization.py` | FIX-2                                                              |
| `test_is_training_false_not_fallthrough` | `test_response_normalization.py` | FIX-2 edge                                                         |
| `test_get_current_metrics_unwraps`       | `test_response_normalization.py` | FIX-3                                                              |
| `test_get_status_normalizes_cascor`      | `test_response_normalization.py` | FIX-4                                                              |
| `test_get_status_epoch_zero_preserved`   | `test_response_normalization.py` | FIX-4 edge                                                         |
| `test_get_status_uppercase_started`      | `test_response_normalization.py` | FIX-4 case                                                         |
| `test_get_status_passthrough_flat`       | `test_response_normalization.py` | FIX-4 demo compat                                                  |
| `test_is_training_in_progress_real`      | `test_cascor_service_adapter.py` | FIX-8                                                              |
| `test_is_training_active_service`        | `test_service_backend.py`        | FIX-8: protocol path through `ServiceBackend.is_training_active()` |
| `test_get_status_partial_nested`         | `test_response_normalization.py` | FIX-4: handles partial nested structure (e.g., missing `monitor`)  |
| `test_metrics_loss_zero_preserved`       | `test_response_normalization.py` | FIX-13 edge                                                        |

#### Verification, Phase 2

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v
# Expected: All Phase 0 tests now PASS
pytest tests/unit/test_service_backend.py -v
pytest tests/unit/ -v -k "service"
```

---

### Phase 3: Fix State Sync on Connect (CRITICAL — Correct Initial State)

**Priority**: Critical — dashboard shows wrong initial state
**Scope**: `canopy/src/backend/state_sync.py`
**Estimated time**: 1.5 hours
**Depends on**: Phase 1 (uses `_first_defined()`)

Fix `CascorStateSync.sync()` to correctly navigate real cascor's nested
response structure. Can run **in parallel** with Phase 2 (touches different
files).

#### 3.1 Fix Training Status Parsing (FIX-5, FIX-12)

**File**: `canopy/src/backend/state_sync.py` (lines 57-65)

```python
from backend.cascor_service_adapter import _first_defined

# Inside sync():
status_response = self._client.get_training_status()
data = status_response.get("data", {})

if isinstance(data, dict):
    # is_training: explicit None check prevents False falling through
    is_training_top = status_response.get("is_training")  # FakeCascorClient
    if is_training_top is not None:
        state.is_training = is_training_top
    else:
        state.is_training = data.get("training_active", False)  # Real server

    # State string from nested structure
    sm = data.get("state_machine", {})
    ts = data.get("training_state", {})
    raw_state = (
        data.get("state")  # FakeCascorClient: data.state
        or (sm.get("status", "").lower() if isinstance(sm, dict) else None)
        or (sm.get("current_state", "").lower() if isinstance(sm, dict) else None)
        or "idle"
    )
    state.status = self._normalize_status(raw_state)

    # Phase (not previously extracted)
    raw_phase = (
        sm.get("phase") if isinstance(sm, dict) else None
    ) or (
        ts.get("phase") if isinstance(ts, dict) else None
    ) or "Idle"
    state.phase = raw_phase.lower() if isinstance(raw_phase, str) else "idle"

    # Epoch and max_epochs: _first_defined preserves 0
    monitor = data.get("monitor", {})
    state.current_epoch = _first_defined(
        data.get("epoch"),                  # FakeCascorClient
        monitor.get("current_epoch") if isinstance(monitor, dict) else None,
        ts.get("current_epoch") if isinstance(ts, dict) else None,
        default=0,
    )
    state.max_epochs = _first_defined(
        data.get("max_epochs"),             # FakeCascorClient
        ts.get("max_epochs") if isinstance(ts, dict) else None,
        ts.get("epochs_max") if isinstance(ts, dict) else None,
        default=0,
    )
else:
    state.is_training = status_response.get("is_training", False)
    state.status = "Stopped"
    state.phase = "idle"
    state.current_epoch = 0
    state.max_epochs = 0
```

**FIX-12: Expand `_normalize_status()` mapping:**

```python
# Add uppercase entries for real server compatibility
mapping = {
    "idle": "Stopped",
    "training": "Started",
    "started": "Started",     # Real server state_machine.status (lowercased)
    "paused": "Paused",
    "complete": "Completed",
    "completed": "Completed", # Real server state_machine.status (lowercased)
    "failed": "Failed",
    "stopped": "Stopped",
    "running": "Started",
}
```

#### 3.2 Fix Metrics History Extraction (FIX-6)

```python
history_response = self._client.get_metrics_history(count=metrics_limit)
if isinstance(history_response, dict):
    data = history_response.get("data", history_response)
    if isinstance(data, list):
        state.metrics_history = data            # Real server: data is the list
    elif isinstance(data, dict):
        state.metrics_history = data.get("history", [])  # FakeCascorClient
    else:
        state.metrics_history = []
elif isinstance(history_response, list):
    state.metrics_history = history_response
```

#### 3.3 Fix Training Params Extraction (FIX-7)

```python
params_response = self._client.get_training_params()
data = params_response.get("data", {})
if isinstance(data, dict):
    state.params = data.get("params", {})       # FakeCascorClient: data.params
    if not state.params:
        # Real server: params are flat fields in data
        state.params = {
            k: v for k, v in data.items()
            if k not in ("epochs", "dataset", "status", "meta", "timestamp")
        }
```

#### Tests for Phase 3

| Test                                    | File                 | Validates                 |
|-----------------------------------------|----------------------|---------------------------|
| `test_sync_real_training_status`        | `test_state_sync.py` | FIX-5: nested status      |
| `test_sync_fake_training_status`        | `test_state_sync.py` | FIX-5: fake compat        |
| `test_sync_is_training_false_preserved` | `test_state_sync.py` | FIX-5: False edge         |
| `test_sync_epoch_zero_preserved`        | `test_state_sync.py` | FIX-5: 0 edge             |
| `test_sync_metrics_history_list`        | `test_state_sync.py` | FIX-6: bare list          |
| `test_sync_metrics_history_dict`        | `test_state_sync.py` | FIX-6: dict compat        |
| `test_sync_params_flat`                 | `test_state_sync.py` | FIX-7: flat params        |
| `test_sync_params_nested`               | `test_state_sync.py` | FIX-7: nested compat      |
| `test_normalize_status_uppercase`       | `test_state_sync.py` | FIX-12: STARTED → Started |
| `test_sync_phase_extracted`             | `test_state_sync.py` | FIX-5: phase population   |

#### Verification, Phase 3

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_state_sync.py -v
```

---

### Phase 4: Parameter Mapping, Dataset & Topology (IMPORTANT)

**Priority**: Important — affects parameter display, dataset tab, topology
**Scope**: canopy only
**Estimated time**: 1.5 hours
**Depends on**: Phase 2

#### 4.1 Fix Reverse Parameter Map (FIX-9)

**File**: `canopy/src/backend/cascor_service_adapter.py` (lines 332-340)

Replace the manually-maintained reverse map with an auto-generated one:

```python
_CASCOR_TO_CANOPY_PARAM_MAP = {v: k for k, v in _CANOPY_TO_CASCOR_PARAM_MAP.items()}
```

This guarantees mathematical consistency and prevents future drift.

> **Semantic verification caveat**: Before applying, verify that
> `nn_growth_convergence_threshold` and `cn_training_convergence_threshold`
> are not legitimately different parameters in the dashboard UI. If both
> exist and map to different cascor params, the asymmetry is intentional
> and the reverse map should remain manually maintained. Check the
> parameter panel component and `main.py` `/api/state` defaults to confirm.

#### 4.2 Harmonize `get_canopy_params()` (FIX-10)

**File**: `canopy/src/backend/cascor_service_adapter.py` (lines 359-375)

Verify and fix the dual-path logic. The current code does:

```python
result = self._client.get_training_params()
params = result.get("data", {}).get("params", {})
```

This attempts the FakeCascorClient format first. The fallback reads flat
params from `data` but needs to filter out non-param keys that appear in
the real server response:

```python
if not params and isinstance(result.get("data"), dict):
    params = {
        k: v for k, v in result.get("data", {}).items()
        if k not in ("epochs", "dataset", "status", "meta", "timestamp")
    }
```

Both paths should return the same canonical param names via
`_CASCOR_TO_CANOPY_PARAM_MAP`.

#### 4.3 Fix Dataset Response Key Mapping (FIX-11)

**File**: `canopy/src/backend/service_backend.py`

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
        # Note: data arrays (inputs, targets) not available from cascor
        # metadata endpoint. See Known Limitations §12.2.
    }
```

#### 4.4 Verify Topology Format (FIX-14)

Compare cascor's `/v1/network/topology` response shape (after
`_unwrap_response()`) against what the network visualizer expects.

**Field-level compatibility checklist:**

- Does the visualizer expect `nodes` array at the top level?
- Does the visualizer expect `connections` array at the top level?
- Does the visualizer expect a `layers` array?
- Do node objects require `id`, `type`, `layer` fields?
- Do connection objects use `from`/`to` or `source_id`/`target_id` keys?
- Does cascor return `hidden_units` array, `output_weights`, `output_bias`
  (weight-oriented format) vs `nodes`, `connections` (graph-oriented)?
- Does `extract_network_topology()` already transform between formats?
- If mismatched, add key transformation in `extract_network_topology()`,
  similar to how `get_decision_boundary()` transforms `grid_x`/`grid_y`
  → `xx`/`yy`.

#### Tests for Phase 4

| Test                                   | File                             | Validates           |
|----------------------------------------|----------------------------------|---------------------|
| `test_param_map_roundtrip_all`         | `test_cascor_service_adapter.py` | FIX-9: all 7 params |
| `test_param_map_reverse_is_inverse`    | `test_cascor_service_adapter.py` | FIX-9: mathematical |
| `test_get_canopy_params_real_envelope` | `test_cascor_service_adapter.py` | FIX-10              |
| `test_get_canopy_params_fake_envelope` | `test_cascor_service_adapter.py` | FIX-10 compat       |
| `test_dataset_key_normalization`       | `test_service_backend.py`        | FIX-11              |
| `test_topology_format_compat`          | `test_service_backend.py`        | FIX-14              |

#### Verification, Phase 4

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_service_controls.py -v
pytest tests/integration/test_param_apply_roundtrip.py -v
pytest tests/ -v -k "dataset or topology or param"
```

---

### Phase 5: FakeCascorClient Alignment (SYSTEMIC)

**Priority**: Important — prevents recurrence of all root cause bugs
**Scope**: juniper-cascor-client
**Estimated time**: 2–3 hours
**Depends on**: Phases 2 and 3 complete (canopy-side fixes validated first)

#### 5.1 Update FakeCascorClient Response Formats (FIX-SYS)

**File**: `juniper-cascor-client/juniper_cascor_client/testing/fake_client.py`

| Method                  | Before                                     | After                                                                                      |
|-------------------------|--------------------------------------------|--------------------------------------------------------------------------------------------|
| All methods             | `"status": "ok"`                           | `"status": "success"`                                                                      |
| All methods             | No `meta` field                            | `"meta": {"timestamp": ..., "version": "0.4.0"}`                                           |
| `get_training_status()` | Top-level `is_training`, flat `data.state` | `data.training_active`, nested `data.state_machine`, `data.monitor`, `data.training_state` |
| `get_metrics_history()` | `data: {"history": [...]}`                 | `data: [... list ...]`                                                                     |
| `get_metrics()`         | Extra `correlation`, `phase`               | Add `timestamp`; keep `train_loss` names                                                   |
| `get_training_params()` | `data: {"params": {...}}`                  | `data: {flat param dict}`                                                                  |

#### 5.2 Add Response Envelope Helper

```python
@staticmethod
def _success_envelope(data: Any) -> Dict[str, Any]:
    return {
        "status": "success",
        "data": data,
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }
```

#### 5.3 Update Affected Tests

This change will break existing tests. Strategy:

1. Update `FakeCascorClient` response format
2. Run full test suite — collect all failures
3. Fix each test to work with new response format
4. Verify all tests pass

Expected breakage in juniper-canopy:

| Test File                                | Expected Impact                 |
|------------------------------------------|---------------------------------|
| `test_cascor_service_adapter.py`         | Mock response format assertions |
| `test_state_sync.py`                     | Status response data paths      |
| `test_fake_service_backend.py`           | Full-chain assertions           |
| `test_service_controls.py`               | Control response message format |
| `test_external_cascor_attach.py`         | Attach response assertions      |
| `test_training_controls_service_mode.py` | Control response shapes         |

#### Verification, Phase 5

```bash
# Cascor-client tests:
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v

# Canopy tests (should all pass after test updates):
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ -v
```

---

### Phase 6: Integration Testing & End-to-End Validation

**Priority**: Critical — validates all fixes work together
**Scope**: canopy + cascor (running)
**Estimated time**: 2 hours
**Depends on**: Phases 2–4 (Phase 5 recommended but optional)

#### 6.1 Required Integration Tests

| Test                                  | File                                               | Type     | Validates                                                                                                                               |
|---------------------------------------|----------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `test_service_mode_dashboard_data`    | `tests/integration/test_dashboard_data.py`         | **Mock** | Each `/api/*` endpoint returns dashboard-compatible shapes in service mode using mocked cascor responses                                |
| `test_external_cascor_attach`         | `tests/integration/test_external_cascor_attach.py` | **Live** | Non-destructive attach to running cascor; no `create_network` or `reset` calls; params/epoch/status populate correctly                  |
| `test_canopy_restart_during_training` | `tests/integration/test_canopy_restart.py`         | **Live** | Start canopy → verify cascor continues → stop canopy → verify cascor keeps running → restart canopy → verify reattach and state restore |
| `test_param_apply_roundtrip`          | `tests/integration/test_param_roundtrip.py`        | **Live** | Apply each mappable param from canopy → verify cascor received update → verify canopy reflects new values                               |

> **CI gating**: Tests marked **(Live)** require a running cascor instance
> and must be gated behind the `CASCOR_BACKEND_AVAILABLE=1` environment
> variable. Tests marked **(Mock)** use mocked cascor responses and run in
> CI without infrastructure. See `AGENTS.md` test environment variables
> for full gating reference.

#### 6.2 Automated Test Suites

**CI-friendly tests** (mock cascor, no infrastructure needed):

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython

# Full unit suite
pytest tests/unit/ -v

# Full integration suite (mock-based, no cascor needed)
pytest tests/integration/ -v -m "not requires_cascor"

# Dashboard data contract tests
pytest tests/integration/test_dashboard_data.py -v

# Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

**Live integration tests** (require running cascor instance):

```bash
# Gate behind env var
export CASCOR_BACKEND_AVAILABLE=1

# Live integration tests
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/integration/test_external_cascor_attach.py -v
pytest tests/integration/test_canopy_restart.py -v
pytest tests/integration/test_param_roundtrip.py -v

# Cascor regression (verify no upstream breakage)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
conda activate JuniperCascor
bash scripts/run_tests.bash

# Cascor-client tests (if Phase 5 was done)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v
```

#### 6.3 Manual End-to-End Verification

```bash
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# Terminal 2: Start canopy (should auto-discover cascor)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: Verify API responses
curl -s http://localhost:8050/api/status | python -m json.tool
curl -s http://localhost:8050/api/metrics/history?limit=10 | python -m json.tool
curl -s http://localhost:8050/api/state | python -m json.tool
curl -s http://localhost:8050/api/dataset | python -m json.tool
curl -s http://localhost:8050/api/topology | python -m json.tool
```

#### 6.4 Visual Verification Checklist

- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Epoch counter shows 0 correctly at training start (not blank)
- [ ] Hidden units count updates on cascade events
- [ ] Loss/accuracy charts display live data
- [ ] Loss chart handles 0.0 values without gaps
- [ ] Phase indicator shows Output/Candidate transitions
- [ ] Network topology renders (topology tab)
- [ ] Decision boundary renders (boundaries tab)
- [ ] Dataset metadata displays (dataset tab)
- [ ] Parameter panel shows actual cascor parameters
- [ ] Parameter changes from canopy apply to cascor
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and shows correct state

---

## 10. Dependency Graph

```bash
Phase 0 (characterization tests)
    └──→ Phase 1 (shared helpers: _first_defined, _normalize_metric, etc.)
              │
              ├──→ Phase 2 (read-path fixes: FIX-1,2,3,4,8,13)
              │         │
              │         └──→ Phase 4 (params, dataset, topology: FIX-9,10,11,14)
              │
              └──→ Phase 3 (state sync: FIX-5,6,7,12)
                        │
                        ▼
                   Phase 5 (FakeCascorClient alignment: FIX-SYS)
                        │
                        ▼
                   Phase 6 (integration testing)
```

- **Phases 2 and 3** can run in **parallel** after Phase 1 (they modify
  different files: `cascor_service_adapter.py`/`service_backend.py` vs
  `state_sync.py`)
- **Phase 4** code changes can start after Phase 2 (uses normalization
  helpers and status contract), but **full QA signoff should wait for
  Phase 3** — parameter display correctness depends on state hydration
  behavior tested in Phase 3
- **Phase 5** should follow Phases 2–3 (validate canopy fixes before
  changing fake client)
- **Phase 6** is the final validation gate

---

## 11. Rollback Strategy

All changes are isolated to the normalization/translation layer. No persistent
data migrations, no schema changes, no new external dependencies.

### If a regression is detected after deployment

1. **Identify scope**: Is the regression in service mode only or does it affect
   demo mode?
2. **Revert the normalization changes**: All production fixes are in three
   files (`cascor_service_adapter.py`, `service_backend.py`, `state_sync.py`).
   Revert these to pre-fix state using `git revert` or `git checkout`.
3. **Redeploy**: The pre-fix codebase remains functional in demo mode.
4. **Verify**: Run characterization tests — they should return to failing
   state, confirming the revert is clean.
5. **Diagnose**: Use the failing characterization test to identify which
   specific normalization path regressed.

### Risk minimization

- All dual-path logic is designed for backward compatibility — FakeCascorClient
  paths are checked first, so demo mode is never affected by normalization
  changes.
- No shared state or database changes — each deploy is independently
  reversible.
- Phase 5 (FakeCascorClient alignment) is the highest-risk change.
  It should be deployed separately from Phases 2–4 and can be reverted
  independently.

---

## 12. Risk Mitigation

| Risk                                                         | Impact                                | Probability  | Mitigation                                                                                                   |
|--------------------------------------------------------------|---------------------------------------|--------------|--------------------------------------------------------------------------------------------------------------|
| Falsy values (epoch=0, loss=0.0) treated as missing          | Charts show gaps; epoch counter blank | Medium       | `_first_defined()` + `"key" in dict` checks; dedicated edge-case tests                                       |
| Real server status case (`STARTED` vs `Started`) mismatch    | Status bar shows wrong state          | Medium       | `.upper()` normalization in `_normalize_status_response`; uppercase entries in `_normalize_status()` mapping |
| FakeCascorClient changes break many tests (Phase 5)          | Test suite fails                      | **High**     | Atomic pass: update fake + fix all tests in one commit. Run full suite before merge                          |
| Dual-path detection misfires                                 | Silent data corruption                | Low          | Positive detection via `_is_cascor_nested()`; test both paths                                                |
| Parameter mapping has untested edge cases                    | Params silently fail to apply         | Medium       | Auto-generated reverse map; round-trip tests for all 7 params                                                |
| Dashboard callbacks have undocumented key dependencies       | Some UI elements still blank          | Medium       | Phase 6 visual verification; explicit dashboard data contract (§6)                                           |
| `_unwrap_response()` strips `meta` field needed by some code | Loss of timestamp/version             | Low          | No current canopy code reads `meta` — verified                                                               |
| Demo mode regresses from shared code changes                 | Demo mode breaks                      | Low          | Dual-path logic checks FakeCascorClient format first                                                         |
| Dataset visualization broken (no data arrays)                | Dataset tab empty scatter plot        | **Expected** | Document as known limitation (§12.2); defer to future enhancement                                            |
| Normalization logic drifts from cascor API                   | Future cascor changes break canopy    | Low          | Phase 5 aligns fake client; tests catch divergence early                                                     |

---

## 13. Success Criteria

### Must Pass (Phase 6 gate)

- [ ] Canopy auto-discovers running cascor and enters service mode
- [ ] All characterization tests pass (Phase 0 tests)
- [ ] Full canopy unit test suite passes with zero failures
- [ ] Full canopy integration test suite passes with zero failures
- [ ] No regressions in cascor test suite
- [ ] `curl /api/status` returns flat dict with `is_running`, `phase`, `current_epoch`
- [ ] `curl /api/metrics/history` returns non-empty `{"history": [...]}` during training
- [ ] `curl /api/metrics` returns unwrapped metric dict (not envelope)
- [ ] Dashboard status bar shows correct Running/Paused/Stopped/Completed state
- [ ] Epoch counter shows actual cascor epoch count (including 0)
- [ ] Metrics charts (loss, accuracy) display live training data

### Should Pass (important)

- [ ] Parameter panel shows actual cascor parameters (not defaults)
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Network topology renders after cascade events
- [ ] State sync correctly hydrates initial state on connect
- [ ] Hidden units counter shows actual cascor hidden unit count
- [ ] Phase indicator shows Output/Candidate/Inference correctly
- [ ] Training controls (start/stop/pause/resume/reset) work in service mode
- [ ] Stopping canopy does not affect cascor training
- [ ] Restarting canopy reconnects and restores current state

### Quality Criteria

- [ ] All existing demo-mode tests continue to pass
- [ ] New tests cover both real server and fake client response formats
- [ ] Test coverage does not decrease
- [ ] No `or` chains used for falsy-value fallback on numeric or boolean fields
- [ ] FakeCascorClient (Phase 5) matches real server ResponseEnvelope format

---

## 14. Files Modified Summary

### juniper-canopy

| File                                             | Phase   | Changes                                                                                                                                                                                                               |
|--------------------------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `src/backend/cascor_service_adapter.py`          | 1, 2, 4 | Add `_first_defined`, `_is_cascor_nested`, `_normalize_metric` helpers; fix monitor methods (FIX-1,2,3); fix `is_training_in_progress` (FIX-8); fix reverse param map (FIX-9); harmonize `get_canopy_params` (FIX-10) |
| `src/backend/service_backend.py`                 | 2, 4    | Add `get_status()` flat-dict builder (FIX-4); fix `get_dataset()` key mapping (FIX-11)                                                                                                                                |
| `src/backend/state_sync.py`                      | 3       | Fix `sync()` field navigation (FIX-5,6,7); expand `_normalize_status()` (FIX-12); add phase extraction                                                                                                                |
| `src/main.py`                                    | —       | No changes needed                                                                                                                                                                                                     |
| `src/tests/fixtures/cascor_response_fixtures.py` | 0       | **NEW** — Real cascor response fixtures                                                                                                                                                                               |
| `src/tests/unit/test_response_normalization.py`  | 0       | **NEW** — Characterization tests                                                                                                                                                                                      |
| `src/tests/unit/test_state_sync.py`              | 3       | Updated with real envelope format tests                                                                                                                                                                               |
| `src/tests/unit/test_service_backend.py`         | 2, 4    | Status normalization + dataset + topology tests                                                                                                                                                                       |
| `src/tests/unit/test_cascor_service_adapter.py`  | 2, 4    | FIX-8 + param roundtrip tests                                                                                                                                                                                         |
| `src/tests/integration/test_dashboard_data.py`   | 6       | **NEW** — Mock: service mode dashboard data shape contract tests                                                                                                                                                      |
| `src/tests/integration/test_canopy_restart.py`   | 6       | **NEW** — Live: canopy restart during training verification                                                                                                                                                           |
| `src/tests/integration/test_param_roundtrip.py`  | 6       | **NEW** — Live: param apply round-trip verification                                                                                                                                                                   |

### juniper-cascor-client (Phase 5 only)

| File                                           | Phase | Changes                                                    |
|------------------------------------------------|-------|------------------------------------------------------------|
| `juniper_cascor_client/testing/fake_client.py` | 5     | Align response format with real ResponseEnvelope (FIX-SYS) |

### juniper-canopy test updates (Phase 5)

| File                                                           | Phase | Changes                            |
|----------------------------------------------------------------|-------|------------------------------------|
| `src/tests/unit/test_cascor_service_adapter.py`                | 5     | Update mock response formats       |
| `src/tests/unit/test_state_sync.py`                            | 5     | Update expected data paths         |
| `src/tests/unit/test_service_backend.py`                       | 5     | Update status response assertions  |
| `src/tests/integration/test_fake_service_backend.py`           | 5     | Update full-chain assertions       |
| `src/tests/integration/test_external_cascor_attach.py`         | 5     | Update attach response assertions  |
| `src/tests/integration/test_training_controls_service_mode.py` | 5     | Update control response assertions |

### No Changes Required

| Repo                              | Reason                                                                    |
|-----------------------------------|---------------------------------------------------------------------------|
| juniper-cascor                    | Server API already exposes all necessary endpoints correctly              |
| juniper-cascor-client (client.py) | Client correctly returns raw responses; normalization is canopy's concern |

---

## 15. Known Limitations & Future Enhancements

### 15.1 WebSocket Buffer Not Consumed by Dash Callbacks

The `websocket_client.js` correctly receives and buffers metrics messages from
the cascor relay (`/ws/training`), but no Dash callback consumes
`window.cascorWS.getBufferedMessages()`. All dashboard data is driven
exclusively via HTTP polling (`dcc.Interval` → `/api/*` endpoints).

**Impact**: Dashboard updates limited to polling frequency (1s fast, 5s slow).
**Future**: Wire `clientside_callback` to consume WebSocket buffer and update
`dcc.Store` directly.

### 15.2 Dataset Visualization Missing Data Arrays in Service Mode

Cascor's `/v1/dataset` endpoint returns metadata only — not actual data
arrays (`inputs`, `targets`). In service mode, the dataset scatter plot
cannot render.

**Impact**: Dataset tab shows metadata only; scatter plot is empty.
**Future**: Add cascor endpoint for dataset arrays, or fetch via
`juniper-data-client`.

### 15.3 `BackendProtocol` Does Not Define Response Shapes

The protocol specifies `Dict[str, Any]` return types but not the expected
response schemas. This allowed `DemoBackend` and `ServiceBackend` to produce
different shapes.

**Future**: Define response schemas (TypedDicts) in `protocol.py`. The
canonical contracts in §6 of this document serve as the specification.

### 15.4 `main.py` Accesses `backend._adapter` Directly

Multiple places access `backend._adapter` (a `ServiceBackend` implementation
detail) rather than going through `BackendProtocol`.

**Future**: Expose needed functionality through protocol methods.

### 15.5 `CascorStateSync` Uses Raw Client Instead of Adapter

`CascorStateSync` is instantiated with the raw `_client` reference and
duplicates envelope handling logic that lives in the adapter. After Phase 3
fixes, this duplication is contained but not eliminated.

**Future**: Refactor `CascorStateSync` to use adapter methods, eliminating
duplicated normalization code.

---

## 16. Verification Commands Summary

```bash
# Phase 0: Run characterization tests (expect failures)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/unit/test_response_normalization.py -v

# Phase 2-3: Run affected unit tests
pytest tests/unit/test_response_normalization.py -v    # expect PASS now
pytest tests/unit/test_state_sync.py -v
pytest tests/unit/test_service_backend.py -v
pytest tests/unit/ -v -k "service"

# Phase 4: Run param and dataset tests
pytest tests/unit/test_service_controls.py -v
pytest tests/integration/test_param_apply_roundtrip.py -v

# Phase 5: Run full suite after FakeCascorClient update
pytest tests/ -v

# Phase 6: Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Cascor regression
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
conda activate JuniperCascor
bash scripts/run_tests.bash

# Cascor-client (after Phase 5)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v

# Manual E2E (Terminal 1: cascor, Terminal 2: canopy, Terminal 3: curl)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# (separate terminal)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
uvicorn main:app --host 0.0.0.0 --port 8050

# (separate terminal)
curl -s http://localhost:8050/api/status | python -m json.tool
curl -s http://localhost:8050/api/metrics/history?limit=10 | python -m json.tool
curl -s http://localhost:8050/api/state | python -m json.tool
```
