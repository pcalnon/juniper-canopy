# External CasCor Integration: Unified Development Plan

**Version**: 3.0.0
**Date**: 2026-03-26
**Status**: Ready for Implementation
**Synthesized from**:

- `EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md` (v2.0.0, Claude)
- `DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md` (v1.0.0, Amp)
- Codebase validation by specialized analysis agents

**Upstream analysis**:

- `CANOPY_EXTERNAL_CASCOR_PLAN.md` — Original gap analysis
- `ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md` — Root cause analysis
- `CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md` — Data flow investigation

---

## 1. Executive Summary

When juniper-canopy connects to an externally running juniper-cascor instance,
the dashboard displays no training data. All data paths from cascor through
the service backend to the dashboard are broken. This plan addresses
**5 confirmed root causes** and **6 additional issues** identified through
cross-codebase analysis, validated against the actual source code.

All issues trace to a single systemic problem: **canopy's service backend
returns raw cascor API responses, but the dashboard was built against the demo
backend's flat response format.** The `_ServiceTrainingMonitor` and
`CascorStateSync` classes were developed against `FakeCascorClient`, whose
response format structurally diverges from the real cascor server's
`ResponseEnvelope`.

### Fix Strategy

Add a **canonical normalization layer** in `CascorServiceAdapter` that
transforms cascor's native API responses into the shapes the dashboard
already consumes. This centralizes all format translation in one place,
avoids breaking changes to the client library, and ensures the monitor and
state sync classes never see raw cascor envelopes.

### Scope

- **juniper-canopy** (primary): All normalization, status transformation,
  and test changes
- **juniper-cascor-client** (secondary, Phase 5 only): `FakeCascorClient`
  alignment
- **juniper-cascor**: No changes required

**Estimated effort**: 8–12 hours across 7 phases

---

## 2. Validated Root Causes & Issues

The following issues were **confirmed by reading actual source code** across
all three codebases. Three claims from the original gap analysis were refuted.

### Confirmed Issues

| ID | Severity | Location | Issue | Impact |
|----|----------|----------|-------|--------|
| RC-1 | **CRITICAL** | `cascor_service_adapter.py:74-79` | `get_recent_metrics()` uses `result.get("history", [])` but real cascor returns `{"status":"success","data":[...list...]}`; key `"history"` never exists | Metrics panels permanently empty |
| RC-2 | **CRITICAL** | `cascor_service_adapter.py:60-66` + `:282-284` | `is_training` and `is_training_in_progress()` read `status.get("is_training", False)` but real cascor nests `training_active` inside `data` | Always returns `False`; health/controls broken |
| RC-3 | **MODERATE** | `cascor_service_adapter.py:68-72` | `get_current_metrics()` returns full ResponseEnvelope without unwrapping | Returns `{"status","data","meta"}` instead of metrics dict |
| RC-4 | **MODERATE** | `state_sync.py:57-65` | `sync()` reads `is_training`, `data.state`, `data.epoch`, `data.max_epochs` — all at wrong nesting levels | State hydration shows Stopped/epoch=0 during active training |
| RC-5 | **SYSTEMIC** | `cascor-client/testing/fake_client.py` | FakeCascorClient response format diverges from real server in every method | All tests pass against fake but fail against real cascor |
| ISS-1 | **CRITICAL** | `service_backend.py:100-101` | `get_status()` returns cascor's nested structure but dashboard reads flat keys (`is_running`, `phase`, `current_epoch`, `hidden_units`) | Status bar, phase display, epoch counter all show defaults |
| ISS-2 | **MODERATE** | `cascor_service_adapter.py:322-338` | `_CASCOR_TO_CANOPY_PARAM_MAP` has asymmetric reverse mapping: forward maps `nn_growth_convergence_threshold` → `patience` but reverse maps `patience` → `cn_training_convergence_threshold` | Param sync applies to wrong canopy field |
| ISS-3 | **CRITICAL** | Multiple files | **Confirmed by codebase validation.** Cascor metrics use `loss`, `accuracy`, `validation_loss`, `validation_accuracy`; dashboard expects `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy` | Metric values silently missing from plots even after envelope fix |
| ISS-4 | **LOW** | `service_backend.py` / cascor API | Dataset endpoint returns metadata only (`train_samples`, `input_features`) but dashboard expects (`num_samples`, `num_features`) with different key names | Dataset tab metadata incorrect |
| ISS-5 | **CRITICAL** | `cascor_service_adapter.py:411-418` | **Confirmed by codebase validation.** `extract_network_topology()` returns raw cascor format (`input_size`, `output_size`) but frontend expects `input_units`, `output_units` | Network visualizer renders empty topology |
| ISS-6 | **MODERATE** | `state_sync.py:57-98` | `SyncedState.phase` is never populated in `sync()` — always defaults to `"Idle"` | Phase display incorrect on initial connect |

### Refuted Claims (from original gap analysis)

| Claim | Status | Evidence |
|-------|--------|----------|
| Gap 1: `create_backend()` reads raw env vars instead of settings | **Refuted** | `__init__.py:56-85` uses `get_settings()` first; raw env vars are legacy fallbacks |
| Gap 2: `initialize()` never calls `CascorStateSync.sync()` | **Refuted** | `service_backend.py:142` calls `CascorStateSync(self._adapter._client).sync()` |
| Gap 4: Discovery mutates `os.environ` but settings already cached | **Refuted** | Discovery passes URL directly via `create_backend(service_url=discovered_url)` |

### Items Confirmed Already Implemented

| Item | Evidence |
|------|----------|
| `/api/state` service mode handling | `main.py:583-615` — populates defaults and calls `get_canopy_params()` |
| Relay state callback | `cascor_service_adapter.py:189-206` — calls `_state_update_callback` for `state` and `event` messages |
| State callback wiring in lifespan | `main.py:202` — registers `training_state.update_state` |
| Topology refresh on `cascade_add` | Relay loop handles `cascade_add`, fetches and broadcasts topology |

---

## 3. Response Format Divergence Reference

### Training Status

| Aspect | FakeCascorClient | Real CasCor Server |
|--------|------------------|--------------------|
| Status field | `"status": "ok"` | `"status": "success"` |
| Training flag | Top-level `"is_training": bool` | `data.training_active: bool` |
| State string | `data.state: "training"` | `data.state_machine.status: "Started"` |
| Epoch | `data.epoch: int` | `data.monitor.current_epoch: int` |
| Meta field | Absent | `"meta": {"timestamp": float, "version": str}` |

### Metrics History

| Aspect | FakeCascorClient | Real CasCor Server |
|--------|------------------|--------------------|
| Data shape | `data: {"history": [...], "total": N, "returned": N}` | `data: [...]` (bare list) |
| Metric field names | `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy` | `loss`, `accuracy`, `validation_loss`, `validation_accuracy` |

### Training Params

| Aspect | FakeCascorClient | Real CasCor Server |
|--------|------------------|--------------------|
| Data shape | `data: {"params": {...}, "epochs": int}` | `data: {"learning_rate": float, ...}` (flat) |

### Network Topology

| Aspect | CasCor Client | Dashboard Frontend |
|--------|---------------|--------------------|
| Input size key | `input_size` | `input_units` |
| Output size key | `output_size` | `output_units` |
| Nodes detail | Detailed `{id, type, layer, activation, bias}` | Not used — reconstructs from unit counts |
| Layers array | Present | Not used |

---

## 4. Architecture: Centralized Normalization Layer

### Why Centralized (Option B) Over Distributed Fixes (Option A)

Two architectural approaches were evaluated:

- **Option A (distributed)**: Fix each method individually with dual-path
  logic (`if "is_training" in status → fake path; else → real path`)
- **Option B (centralized)**: Add normalization methods to
  `CascorServiceAdapter` that all consumers call

**Option B is selected** for these reasons:

1. **Maintainability**: A cascor API change requires updating one normalizer,
   not hunting through every method
2. **Single responsibility**: The monitor monitors; the adapter adapts
3. **Eliminates dual-path drift**: Both response formats flow through the
   same normalizer, producing identical output shapes
4. **Prevents ISS-3 class bugs**: Field name normalization happens once, not
   at every consumption site

### Data Flow After Fix

```
juniper-cascor (REST API)
  │ ResponseEnvelope: {"status":"success","data":...,"meta":...}
  ▼
juniper-cascor-client (JuniperCascorClient)
  │ Returns raw response.json() — no unwrapping (unchanged)
  ▼
CascorServiceAdapter (canopy — NORMALIZATION LAYER)
  │ _unwrap_envelope()         → strips status/data/meta
  │ _normalize_status()        → flat dict matching DemoBackend
  │ _normalize_metric()        → canonical metric field names
  │ _normalize_metrics_history() → list of normalized metrics
  │ _normalize_topology()      → input_units/output_units/connections
  │ _normalize_dataset()       → canopy key names
  │ _first_defined()           → safe falsy-value extraction
  ▼
ServiceBackend / _ServiceTrainingMonitor
  │ Consume normalized data (same shape as DemoBackend)
  ▼
main.py REST endpoints → Dashboard callbacks
```

### Critical Safety Measures (from Proposal A)

Even with centralized normalization, these safety measures are essential:

1. **`_first_defined()` helper**: Avoids `or` chains where `epoch=0` or
   `hidden_units=0` would be treated as missing (falsy). Uses explicit
   `is not None` checks.
2. **`is_training` explicit None check**: `bool(False)` is falsy — a simple
   truthiness check cannot distinguish "not training" from "field absent."
3. **Strict envelope detection**: `_unwrap_envelope()` requires `"data"` AND
   (`"meta"` OR `"status"`) to avoid false positives on responses that
   legitimately contain a `"data"` field.

---

## 5. Gap Reconciliation

Cross-referencing `CANOPY_EXTERNAL_CASCOR_PLAN.md` (v1) gaps against current
codebase:

| Gap | Original Description | Current Status | Action |
|-----|---------------------|----------------|--------|
| Gap 1 | Backend factory ignores settings | **Refuted** — factory reads settings first | None |
| Gap 2 | State not hydrated on connect | **Refuted** — `initialize()` calls `sync()` | Fix `sync()` field navigation (Phase 3) |
| Gap 3 | `/api/state` defaults in service mode | **Already implemented** (main.py:583-615) | Verify `get_canopy_params()` envelope handling |
| Gap 4 | Discovery env var mutation | **Refuted** — URL passed directly | None |
| Gap 5 | Parameter mapping incomplete | **Resolved** — 7 entries in both maps | Fix reverse map asymmetry (Phase 4) |
| Gap 6 | No topology refresh on cascade events | **Already implemented** in relay loop | None |
| Gap 7 | Response normalization inconsistent | **Open** — monitor bypasses `_unwrap_response()` | Fix in Phase 2 |
| Gap 8 | Local training_state drifts | **Already implemented** (adapter:189-206) | None |
| Gap 9 | Auth env var miswired | **Needs verification** | Verify in Phase 2 |

---

## 6. Phased Implementation Plan

### Phase 0: Characterization Tests

**Priority**: Prerequisite
**Scope**: canopy tests only
**Estimated time**: 45 min
**Depends on**: Nothing

Write characterization tests that capture the **current broken behavior**
of the service backend with real cascor response formats. These tests will
initially **fail** (documenting the bugs), then pass after fixes are applied.

#### Changes

1. **`src/tests/fixtures/cascor_response_fixtures.py`** — **NEW**

   Reusable fixtures containing real cascor ResponseEnvelope-formatted
   responses:
   - `real_training_status_response()` — nested `state_machine`, `monitor`,
     `training_state`
   - `real_metrics_history_response()` — `data` as flat list with cascor
     field names (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`)
   - `real_metrics_current_response()` — single metric in envelope
   - `real_training_params_response()` — flat param dict in envelope
   - `real_topology_response()` — `input_size`, `output_size` format
   - `real_dataset_response()` — metadata-only format

2. **`src/tests/unit/test_response_normalization.py`** — **NEW**

   Test cases (expected to FAIL before fixes, PASS after):
   - `test_get_recent_metrics_with_real_envelope` — RC-1
   - `test_is_training_with_real_envelope` — RC-2
   - `test_is_training_in_progress_with_real_envelope` — RC-2 second path
   - `test_get_current_metrics_with_real_envelope` — RC-3
   - `test_get_status_returns_flat_dict` — ISS-1
   - `test_state_sync_with_real_envelope` — RC-4
   - `test_metrics_field_normalization` — ISS-3
   - `test_topology_key_normalization` — ISS-5
   - `test_epoch_zero_not_treated_as_missing` — falsy-value edge case
   - `test_is_training_false_not_fallthrough` — falsy-value edge case

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v
# Expected: tests FAIL (documenting current bugs)
```

---

### Phase 1: Normalization Infrastructure

**Priority**: Critical — foundation for all subsequent phases
**Scope**: `canopy/src/backend/cascor_service_adapter.py`
**Estimated time**: 1 hour
**Depends on**: Phase 0 (tests written)

Add the normalization methods that all subsequent fixes will use. This phase
adds infrastructure only — it does not yet wire the methods into the monitor
or backend.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Add normalization methods:

   ```python
   @staticmethod
   def _unwrap_envelope(response: Any) -> Any:
       """Strip ResponseEnvelope, returning the 'data' payload.

       Detection requires 'data' AND a secondary signal ('meta' or
       'status') to avoid false-positives on responses that
       legitimately contain a 'data' field.
       """
       if isinstance(response, dict) and "data" in response and (
           "meta" in response or "status" in response
       ):
           return response["data"]
       return response

   @staticmethod
   def _first_defined(*values, default=None):
       """Return the first value that is not None, or default.

       Avoids the 'or' chain pitfall where valid falsy values
       (0, False, '') are skipped.
       """
       for v in values:
           if v is not None:
               return v
       return default

   @staticmethod
   def _normalize_metric(item: dict) -> dict:
       """Normalize a single metric entry to canopy's field names.

       Cascor uses: loss, accuracy, validation_loss, validation_accuracy
       Canopy uses: train_loss, train_accuracy, val_loss, val_accuracy
       """
       return {
           "epoch": item.get("epoch", 0),
           "train_loss": item.get("train_loss") or item.get("loss"),
           "train_accuracy": item.get("train_accuracy") or item.get("accuracy"),
           "val_loss": item.get("val_loss") or item.get("validation_loss"),
           "val_accuracy": item.get("val_accuracy") or item.get("validation_accuracy"),
           "hidden_units": item.get("hidden_units", 0),
           "phase": item.get("phase") or item.get("cascade_phase"),
           "timestamp": item.get("timestamp"),
       }

   @staticmethod
   def _normalize_metrics_history(response: Any) -> list:
       """Extract and normalize metrics history from cascor response."""
       data = CascorServiceAdapter._unwrap_envelope(response)
       if isinstance(data, list):
           return [CascorServiceAdapter._normalize_metric(m) for m in data]
       if isinstance(data, dict):
           history = data.get("history", [])
           return [CascorServiceAdapter._normalize_metric(m) for m in history]
       return []

   @staticmethod
   def _normalize_topology(data: dict) -> dict:
       """Normalize cascor topology to frontend format.

       Cascor uses: input_size, output_size
       Frontend expects: input_units, output_units, hidden_units, connections
       """
       return {
           "input_units": data.get("input_units") or data.get("input_size", 0),
           "output_units": data.get("output_units") or data.get("output_size", 0),
           "hidden_units": data.get("hidden_units", 0),
           "connections": data.get("connections", []),
           "nodes": data.get("nodes", []),
           "total_connections": data.get("total_connections", 0),
       }

   @staticmethod
   def _normalize_dataset(data: dict) -> dict:
       """Normalize cascor dataset metadata to canopy format."""
       return {
           "loaded": data.get("loaded", False),
           "num_samples": data.get("num_samples")
               or (data.get("train_samples", 0) + data.get("test_samples", 0)),
           "num_features": data.get("num_features") or data.get("input_features", 0),
           "num_classes": data.get("num_classes") or data.get("output_features", 0),
           "train_samples": data.get("train_samples", 0),
           "test_samples": data.get("test_samples", 0),
       }
   ```

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
python -c "from backend.cascor_service_adapter import CascorServiceAdapter; print('imports ok')"
```

---

### Phase 2: Monitor, Status & Adapter Fixes

**Priority**: Critical — unblocks all dashboard display
**Scope**: `cascor_service_adapter.py`, `service_backend.py`
**Estimated time**: 1.5 hours
**Depends on**: Phase 1 (normalization methods available)

Wire the normalization infrastructure into `_ServiceTrainingMonitor`,
`CascorServiceAdapter.is_training_in_progress()`, and
`ServiceBackend.get_status()`. This fixes RC-1, RC-2, RC-3, ISS-1, ISS-3,
and ISS-5.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Fix `_ServiceTrainingMonitor`:

   **RC-1: `get_recent_metrics()` (lines 74-79):**

   ```python
   def get_recent_metrics(self, count: int = 100) -> list:
       try:
           result = self._client.get_metrics_history(count=count)
           return CascorServiceAdapter._normalize_metrics_history(result)
       except JuniperCascorClientError:
           return []
   ```

   **RC-2: `is_training` property (lines 60-66):**

   ```python
   @property
   def is_training(self) -> bool:
       try:
           status = self._client.get_training_status()
           data = CascorServiceAdapter._unwrap_envelope(status)
           if isinstance(data, dict):
               # Check both real server and fake client field names
               is_active = data.get("training_active")
               if is_active is not None:
                   return is_active
               monitor = data.get("monitor", {})
               if isinstance(monitor, dict) and "is_training" in monitor:
                   return monitor["is_training"]
           # FakeCascorClient compat: top-level is_training
           return status.get("is_training", False)
       except JuniperCascorClientError:
           return False
   ```

   **RC-3: `get_current_metrics()` (lines 68-72):**

   ```python
   def get_current_metrics(self) -> Dict[str, Any]:
       try:
           result = self._client.get_metrics()
           data = CascorServiceAdapter._unwrap_envelope(result)
           return CascorServiceAdapter._normalize_metric(data) if isinstance(data, dict) else data
       except JuniperCascorClientError:
           return {}
   ```

2. **`src/backend/cascor_service_adapter.py`** — Fix `is_training_in_progress()`
   (lines 282-284):

   Apply the same envelope unwrapping as `is_training` above. Both methods
   must use identical logic.

3. **`src/backend/cascor_service_adapter.py`** — Fix `extract_network_topology()`
   (lines 411-418):

   **ISS-5:**

   ```python
   def extract_network_topology(self) -> Optional[Dict[str, Any]]:
       try:
           raw = self._unwrap_response(self._client.get_topology())
           if not raw or not isinstance(raw, dict):
               return None
           return self._normalize_topology(raw)
       except JuniperCascorClientError:
           return None
   ```

4. **`src/backend/service_backend.py`** — Replace `get_status()`:

   **ISS-1:** Build a flat dict matching `DemoBackend.get_status()`:

   ```python
   def get_status(self) -> Dict[str, Any]:
       raw = self._adapter.get_training_status()
       return self._normalize_status_response(raw)

   @staticmethod
   def _normalize_status_response(raw: Dict[str, Any]) -> Dict[str, Any]:
       """Transform cascor's nested training status into flat dashboard format."""
       # Detect cascor's nested structure positively
       if not isinstance(raw, dict) or (
           "state_machine" not in raw and "training_active" not in raw
       ):
           return raw  # Already flat (demo-compatible)

       _fd = CascorServiceAdapter._first_defined
       sm = raw.get("state_machine", {}) if isinstance(raw.get("state_machine"), dict) else {}
       monitor = raw.get("monitor", {}) if isinstance(raw.get("monitor"), dict) else {}
       ts = raw.get("training_state", {}) if isinstance(raw.get("training_state"), dict) else {}

       current_state = (
           sm.get("status", "").upper()
           or sm.get("current_state", "").upper()
       )

       return {
           "is_training": raw.get("training_active", False),
           "is_running": current_state in ("STARTED", "RUNNING", "TRAINING"),
           "is_paused": current_state == "PAUSED",
           "completed": current_state in ("COMPLETED", "CONVERGED"),
           "failed": current_state == "FAILED",
           "fsm_status": current_state,
           "phase": sm.get("phase") or ts.get("phase", "idle"),
           "current_epoch": _fd(
               monitor.get("current_epoch"),
               monitor.get("epoch"),
               ts.get("current_epoch"),
               default=0,
           ),
           "hidden_units": _fd(
               monitor.get("current_hidden_units"),
               monitor.get("hidden_units"),
               default=0,
           ),
           "network_connected": raw.get("network_loaded", False),
           "monitoring_active": current_state in ("STARTED", "RUNNING", "TRAINING"),
       }
   ```

5. **`src/backend/service_backend.py`** — Fix `get_dataset()`:

   **ISS-4:**

   ```python
   def get_dataset(self) -> Optional[Dict[str, Any]]:
       raw = self._adapter.get_dataset_info()
       if not raw:
           return None
       return CascorServiceAdapter._normalize_dataset(raw)
   ```

6. **`src/backend/__init__.py`** — Verify API key env var:

   Confirm `create_backend()` uses `JUNIPER_CASCOR_API_KEY` (not
   `JUNIPER_DATA_API_KEY`). Quick check, likely no change needed.

#### Dashboard Key Mapping Reference

| Dashboard Key | Cascor Source Path | DemoBackend Equivalent |
|---------------|-------------------|----------------------|
| `is_running` | `state_machine.status == "STARTED"` | `fsm.status == "STARTED"` |
| `is_paused` | `state_machine.status == "PAUSED"` | `fsm.status == "PAUSED"` |
| `completed` | `state_machine.status == "COMPLETED"` | `fsm.status == "COMPLETED"` |
| `failed` | `state_machine.status == "FAILED"` | `fsm.status == "FAILED"` |
| `phase` | `state_machine.phase` | `training_phase` |
| `current_epoch` | `monitor.current_epoch` | `current_epoch` |
| `hidden_units` | `monitor.current_hidden_units` | `hidden_units` |
| `is_training` | `training_active` | `is_training` |
| `network_connected` | `network_loaded` | `network is not None` |

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v -k "metrics or is_training or get_current or get_status or topology"
# Expected: RC-1, RC-2, RC-3, ISS-1, ISS-3, ISS-5 tests now PASS
```

---

### Phase 3: State Sync Fix

**Priority**: Critical — correct initial state hydration
**Scope**: `canopy/src/backend/state_sync.py`
**Estimated time**: 45 min
**Depends on**: Phase 1 (uses `_unwrap_envelope`, `_first_defined`)

Fix `CascorStateSync.sync()` to correctly navigate real cascor's nested
response structure. This fixes RC-4 and ISS-6.

#### Design Decision

The current `CascorStateSync` takes a raw client reference and reads
responses directly, duplicating envelope logic. The fix uses the adapter's
normalization methods (via class-level static calls) to share the canonical
unwrapping logic. A future cleanup pass could refactor `CascorStateSync` to
accept the adapter instead of the raw client.

#### Changes

1. **`src/backend/state_sync.py`** — Fix `sync()` training status (lines 57-65):

   ```python
   status_response = self._client.get_training_status()
   data = CascorServiceAdapter._unwrap_envelope(status_response)
   if not isinstance(data, dict):
       data = {}

   # Extract is_training with explicit None check (False is a valid value)
   is_training_top = status_response.get("is_training")  # FakeCascorClient
   if is_training_top is not None:
       state.is_training = is_training_top
   else:
       state.is_training = data.get("training_active", False)

   # Extract state string from nested structure
   sm = data.get("state_machine", {})
   ts = data.get("training_state", {})
   raw_state = (
       data.get("state")  # FakeCascorClient: flat
       or (sm.get("status", "").lower() if isinstance(sm, dict) else None)
       or (sm.get("current_state", "").lower() if isinstance(sm, dict) else None)
       or "idle"
   )
   state.status = self._normalize_status(raw_state)

   # ISS-6: Extract phase (was never populated)
   state.phase = (
       (sm.get("phase") if isinstance(sm, dict) else None)
       or (ts.get("phase") if isinstance(ts, dict) else None)
       or "Idle"
   )

   # Use _first_defined to handle falsy epoch=0 correctly
   _fd = CascorServiceAdapter._first_defined
   monitor = data.get("monitor", {})
   state.current_epoch = _fd(
       data.get("epoch"),
       monitor.get("current_epoch") if isinstance(monitor, dict) else None,
       ts.get("current_epoch") if isinstance(ts, dict) else None,
       default=0,
   )
   state.max_epochs = _fd(
       data.get("max_epochs"),
       ts.get("max_epochs") if isinstance(ts, dict) else None,
       ts.get("epochs_max") if isinstance(ts, dict) else None,
       default=0,
   )
   ```

2. **`src/backend/state_sync.py`** — Fix metrics history (lines 89-93):

   ```python
   history_response = self._client.get_metrics_history(count=metrics_limit)
   state.metrics_history = CascorServiceAdapter._normalize_metrics_history(
       history_response
   )
   ```

3. **`src/backend/state_sync.py`** — Fix params extraction (lines 70-75):

   ```python
   params_response = self._client.get_training_params()
   data = CascorServiceAdapter._unwrap_envelope(params_response)
   if isinstance(data, dict):
       state.params = data.get("params", {})
       if not state.params:
           state.params = {
               k: v for k, v in data.items()
               if k not in ("epochs", "dataset", "status", "meta", "timestamp")
           }
   ```

4. **`src/backend/state_sync.py`** — Fix `_normalize_status()`:

   Ensure it handles real cascor's state names (both cases):

   ```python
   mapping = {
       "idle": "Stopped",
       "training": "Started",
       "started": "Started",
       "paused": "Paused",
       "complete": "Completed",
       "completed": "Completed",
       "failed": "Failed",
       "stopped": "Stopped",
       # Preserve already-normalized values
       "Stopped": "Stopped",
       "Started": "Started",
       "Paused": "Paused",
       "Completed": "Completed",
       "Failed": "Failed",
   }
   ```

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v -k "state_sync"
pytest tests/unit/test_state_sync.py -v
```

---

### Phase 4: Parameter Map & Cleanup

**Priority**: Important — prevents param sync errors
**Scope**: `canopy/src/backend/cascor_service_adapter.py`
**Estimated time**: 30 min
**Depends on**: Phase 1

Fix the asymmetric param map and verify `get_canopy_params()` envelope
handling. This fixes ISS-2.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Generate reverse map
   programmatically:

   ```python
   _CANOPY_TO_CASCOR_PARAM_MAP = {
       "nn_learning_rate": "learning_rate",
       "nn_max_hidden_units": "max_hidden_units",
       "nn_max_total_epochs": "epochs_max",
       "nn_growth_convergence_threshold": "patience",
       "cn_pool_size": "candidate_pool_size",
       "cn_correlation_threshold": "correlation_threshold",
       "cn_training_iterations": "candidate_epochs",
   }

   # Generated from forward map — guaranteed consistent
   _CASCOR_TO_CANOPY_PARAM_MAP = {v: k for k, v in _CANOPY_TO_CASCOR_PARAM_MAP.items()}

   # Bijectivity guard
   assert len(_CASCOR_TO_CANOPY_PARAM_MAP) == len(_CANOPY_TO_CASCOR_PARAM_MAP), \
       "Parameter maps are not bijective — check for duplicate values"
   ```

2. **`src/backend/cascor_service_adapter.py`** — Update `get_canopy_params()`
   to use `_unwrap_envelope()` consistently.

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_service_controls.py -v
pytest tests/unit/test_cascor_service_adapter.py -v -k "param"
```

---

### Phase 5: FakeCascorClient Alignment

**Priority**: Important — prevents future divergence
**Scope**: `juniper-cascor-client/juniper_cascor_client/testing/fake_client.py`
**Estimated time**: 2 hours
**Depends on**: Phases 1-4 (production fixes stable first)

Update `FakeCascorClient` to match real server's `ResponseEnvelope` format.
This fixes RC-5 at the systemic level.

#### Changes

1. **Add `_success_response()` helper:**

   ```python
   def _success_response(self, data: Any) -> dict:
       return {
           "status": "success",
           "data": data,
           "meta": {"timestamp": time.time(), "version": "0.4.0-fake"},
       }
   ```

2. **Update all response methods:**

   | Method | Before | After |
   |--------|--------|-------|
   | All | `"status": "ok"` | `"status": "success"` + `"meta"` |
   | `get_training_status()` | `is_training` at top; flat `data.state` | `data.training_active`; nested `state_machine`, `monitor`, `training_state` |
   | `get_metrics_history()` | `data: {"history": [...]}` | `data: [...]` (bare list) |
   | `get_metrics()` | `data: {train_loss, train_accuracy}` | `data: {loss, accuracy, validation_loss, validation_accuracy}` |
   | `get_training_params()` | `data: {"params": {...}}` | `data: {learning_rate, ...}` (flat) |
   | `get_topology()` | Graph-oriented | `input_size`, `output_size` format |

3. **Update affected test files:**

   | Test File | Expected Breakage |
   |-----------|------------------|
   | `test_cascor_service_adapter.py` | Mock response formats |
   | `test_state_sync.py` | Status response assertions |
   | `test_service_backend.py` | Status response assertions |
   | `test_fake_service_backend.py` | Full-chain assertions |
   | `test_external_cascor_attach.py` | Attach response assertions |
   | `test_service_controls.py` | Control response assertions |
   | `test_training_controls_service_mode.py` | Control response assertions |

   **Strategy**: Update FakeCascorClient → run full suite → collect failures
   → fix each test → verify all pass.

#### Verification

```bash
# Cascor-client tests
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v

# Canopy tests (all)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ -v
```

---

### Phase 6: Integration Testing & E2E Validation

**Priority**: Critical — validates all fixes work together
**Scope**: canopy + cascor
**Estimated time**: 1.5 hours
**Depends on**: Phases 1-4 (Phase 5 recommended)

#### New Integration Tests

> Tests marked `(mock)` run in CI without infrastructure. Tests marked
> `(live)` require a running cascor instance — gated behind
> `CASCOR_BACKEND_AVAILABLE=1`.

| Test | File | Purpose |
|------|------|---------|
| `test_service_mode_dashboard_data` | `tests/integration/test_dashboard_data.py` | (mock) Verify each `/api/*` endpoint returns dashboard-compatible shapes |
| `test_external_cascor_attach` | `tests/integration/test_external_cascor_attach.py` | (live) Non-destructive attach; params/epoch/status populate correctly |
| `test_canopy_restart_during_training` | `tests/integration/test_canopy_restart.py` | (live) Stop/restart canopy; cascor continues; state restores on reattach |
| `test_param_apply_roundtrip` | `tests/integration/test_param_roundtrip.py` | (live) Apply params from canopy → verify cascor received → verify canopy reflects |

#### Characterization Tests Gate

```bash
# All Phase 0 characterization tests must now PASS
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v
```

#### Regression Verification

```bash
# Canopy full suite with coverage
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/ --cov=. --cov-report=term-missing -v

# Cascor regression
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
conda activate JuniperCascor
bash scripts/run_tests.bash

# Cascor-client (after Phase 5)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v
```

#### Manual E2E Verification

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
curl -s http://localhost:8050/api/topology | python -m json.tool
curl -s http://localhost:8050/api/dataset | python -m json.tool
```

#### Visual Verification Checklist

- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Hidden units count updates on cascade events
- [ ] Loss chart plots live data with descending curve
- [ ] Accuracy chart plots live data with ascending curve
- [ ] Phase indicator shows correct training phase
- [ ] Network topology renders with correct structure
- [ ] Decision boundary renders (boundaries tab)
- [ ] Parameter panel shows actual cascor parameters
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and state restores
- [ ] Dataset metadata displays (dataset tab)

---

## 7. Dependency Graph

```
Phase 0 (characterization tests — write failing tests)
    │
    ▼
Phase 1 (normalization infrastructure)
    │
    ├────────────────────────┬─────────────────┐
    ▼                        ▼                 ▼
Phase 2                 Phase 3            Phase 4
(monitor/status/        (state sync)       (param map)
 adapter fixes)
    │                        │                 │
    └────────────┬───────────┘                 │
                 ▼                             │
            Phase 5 (FakeCascorClient) ←───────┘
                 │
                 ▼
            Phase 6 (integration & E2E)
```

- **Phase 0** must complete first (test infrastructure)
- **Phase 1** must complete before any production fixes
- **Phases 2, 3, and 4** can run in parallel after Phase 1
- **Phase 5** should follow all production fixes
- **Phase 6** is the final validation gate

---

## 8. Files Modified Summary

### juniper-canopy (production)

| File | Phase | Changes |
|------|-------|---------|
| `src/backend/cascor_service_adapter.py` | 1, 2, 4 | Add normalization methods; fix `_ServiceTrainingMonitor`; fix `is_training_in_progress`; fix `extract_network_topology`; fix param map |
| `src/backend/service_backend.py` | 2 | Add `_normalize_status_response()`; fix `get_dataset()` |
| `src/backend/state_sync.py` | 3 | Fix `sync()` field navigation; fix `_normalize_status()`; add phase extraction |

### juniper-canopy (tests)

| File | Phase | Changes |
|------|-------|---------|
| `src/tests/fixtures/cascor_response_fixtures.py` | 0 | **NEW** — Real-format response fixtures |
| `src/tests/unit/test_response_normalization.py` | 0 | **NEW** — Characterization tests |
| `src/tests/unit/test_cascor_service_adapter.py` | 2, 4 | Update for envelope unwrapping |
| `src/tests/unit/test_state_sync.py` | 3, 5 | Update for real response format |
| `src/tests/unit/test_service_backend.py` | 2, 5 | Status normalization tests |
| `src/tests/integration/test_dashboard_data.py` | 6 | **NEW** — Service mode data shapes (mock) |
| `src/tests/integration/test_external_cascor_attach.py` | 6 | **NEW** — Live cascor attach |

### juniper-cascor-client (Phase 5 only)

| File | Phase | Changes |
|------|-------|---------|
| `juniper_cascor_client/testing/fake_client.py` | 5 | Align all responses with real `ResponseEnvelope` |

### No changes required

| Repo | Reason |
|------|--------|
| juniper-cascor | Server API already correct; normalization is canopy's responsibility |
| juniper-cascor-client (`client.py`) | Client correctly returns raw JSON; no unwrapping needed |

---

## 9. Risk Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| FakeCascorClient update breaks many tests | Suite fails until tests updated | **High** | Phase 5 as single atomic pass; run full suite before committing |
| Metric field normalization misses a name | Chart shows gaps for that metric | Medium | `_normalize_metric()` uses fallback chain (`train_loss` OR `loss`); test with both |
| Status normalization misses a state value | Dashboard shows wrong status | Medium | Exhaustive state mapping in `_normalize_status()`; test each FSM state |
| `_unwrap_envelope()` false positive | Strips legitimate `data` field | Low | Strict detection requires `data` AND (`meta` OR `status`) |
| `_first_defined()` not used everywhere | Falsy epoch=0 or hidden_units=0 treated as missing | Medium | Grep for `or 0` patterns in adapter/backend code after fixes; replace with `_first_defined()` |
| Topology normalization incomplete | Network visualizer renders incorrectly | Medium | Phase 6 visual verification specifically checks topology |
| Dataset arrays still missing in service mode | Dataset scatter plot empty | **Expected** | Known limitation; document and plan future fix |
| Demo mode regresses from normalization changes | Demo mode breaks | Low | Normalizers are idempotent — already-normalized data passes through unchanged |
| Concurrency: WS state update races with HTTP poll | Inconsistent snapshot | Low | Both update `training_state` additively; thread-safe by design |

---

## 10. Success Criteria

### Functional

- [ ] Canopy auto-discovers running cascor and enters service mode
- [ ] Dashboard shows current cascor status immediately on connect (not defaults)
- [ ] Status bar shows correct Running/Paused/Stopped/Completed state
- [ ] Epoch counter shows actual cascor epoch count (including 0)
- [ ] Hidden units counter shows actual count (including 0)
- [ ] Phase indicator shows Output/Candidate/Inference correctly
- [ ] Metrics charts (loss, accuracy) display live training data
- [ ] Parameters panel shows actual cascor parameters
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Network topology renders with correct structure
- [ ] Training controls (start/stop/pause/resume/reset) work in service mode
- [ ] Stopping canopy does not affect cascor training
- [ ] Restarting canopy reconnects and restores current state

### Quality

- [ ] All Phase 0 characterization tests pass (were failing before fixes)
- [ ] All existing demo-mode tests continue to pass
- [ ] No regressions in cascor test suite
- [ ] New tests cover both real server and fake client response formats
- [ ] Test coverage does not decrease
- [ ] FakeCascorClient matches real server ResponseEnvelope format (Phase 5)

---

## 11. Dashboard Data Contract

Both `DemoBackend` and `ServiceBackend` must produce these response shapes.

### `/api/status`

```python
{
    "is_running": bool,
    "is_paused": bool,
    "completed": bool,
    "failed": bool,
    "phase": str,                # "idle" | "output" | "candidate" | "inference"
    "current_epoch": int,
    "hidden_units": int,
    "fsm_status": str,
    "is_training": bool,
    "network_connected": bool,
    "monitoring_active": bool,
}
```

### `/api/metrics/history`

```python
{
    "history": [
        {
            "epoch": int,
            "train_loss": float,       # Normalized from cascor's "loss"
            "train_accuracy": float,   # Normalized from cascor's "accuracy"
            "val_loss": float | None,  # Normalized from "validation_loss"
            "val_accuracy": float | None,
            "hidden_units": int,
            "phase": str,
        },
    ]
}
```

### `/api/topology`

```python
{
    "input_units": int,            # Normalized from cascor's "input_size"
    "output_units": int,           # Normalized from cascor's "output_size"
    "hidden_units": int,
    "connections": [
        {"from": str, "to": str, "weight": float}
    ],
}
```

### `/api/dataset`

```python
{
    "num_samples": int,            # Normalized from "train_samples" + "test_samples"
    "num_features": int,           # Normalized from "input_features"
    "num_classes": int,            # Normalized from "output_features"
}
```

---

## 12. Known Limitations & Future Enhancements

### 12.1 WebSocket Buffer Not Consumed by Dash Callbacks

The `websocket_client.js` receives and buffers cascor relay messages, but no
Dash callback consumes the buffer. All dashboard data flows via HTTP polling
(1s fast, 5s slow). Sub-second metric updates are received but not rendered.

**Future**: Wire `clientside_callback` to consume WS buffer into `dcc.Store`.

### 12.2 Dataset Scatter Plot Unavailable in Service Mode

Cascor's `/v1/dataset` returns metadata only — no data arrays. The dataset
scatter plot requires `inputs` and `targets` arrays.

**Future**: Fetch data via `juniper-data-client`, or add a cascor endpoint.

### 12.3 `BackendProtocol` Has No Response Schemas

The protocol specifies `Dict[str, Any]` returns without defining shapes.
This allowed the demo and service backends to diverge silently.

**Future**: Define response schemas (TypedDicts) in `protocol.py`.

### 12.4 `main.py` Accesses `backend._adapter` Directly

Multiple places bypass `BackendProtocol` to reach `ServiceBackend._adapter`.

**Future**: Expose needed methods through the protocol interface.

### 12.5 Concurrency Between WebSocket and HTTP Updates

When a WebSocket state update arrives during an HTTP status poll, both write
to `training_state`. The last-write-wins behavior could produce inconsistent
snapshots. This is mitigated by `training_state` being thread-safe and
updates being additive, but not formally addressed.

**Future**: Consider sequencing or versioning state updates.
