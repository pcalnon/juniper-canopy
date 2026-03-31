# Development Plan: External CasCor Dashboard Integration Fix

**Version**: 1.0.0
**Date**: 2026-03-26
**Author**: Amp (AI Agent)
**Status**: Ready for Implementation
**Related Documents**:

- `CANOPY_EXTERNAL_CASCOR_PLAN.md` — Original gap analysis
- `ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md` — Root cause analysis
- `CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md` — Data flow investigation

---

## Executive Summary

When juniper-canopy connects to an externally running juniper-cascor instance,
the dashboard displays no training data. This plan addresses 5 confirmed root
causes and 4 additional issues identified through cross-codebase analysis.
All issues trace to a single systemic problem: **the canopy service backend
returns raw cascor API responses, but the dashboard was built against the demo
backend's flat response format.**

The fix strategy is to add a **canonical Canopy-side translation layer** in
`CascorServiceAdapter` that normalizes cascor's native API responses into
the shapes the dashboard already consumes. This approach avoids breaking
changes to the client library and centralizes all format translation in one
place.

**Estimated effort**: 6–10 hours across all phases
**Repos modified**: juniper-canopy (primary), juniper-cascor-client (tests/fake only)
**Repos unmodified**: juniper-cascor (no server changes required)

---

## Validated Root Causes

The following root causes were **confirmed by reading the actual source code**
across all three codebases. Two gaps from the original plan were refuted.

### Confirmed Issues

| ID | Severity | File | Issue | Impact |
|----|----------|------|-------|--------|
| RC-1 | **CRITICAL** | `cascor_service_adapter.py:74-79` | `get_recent_metrics()` uses `result.get("history", [])` but real cascor returns `{"status":"success","data":[...list...]}`; key `"history"` never exists | Dashboard metrics panels permanently empty |
| RC-2 | **MODERATE** | `cascor_service_adapter.py:60-66` + `:282-284` | `is_training` and `is_training_in_progress()` read `status.get("is_training", False)` but real cascor puts `training_active` inside `data` | Always returns `False`; health/controls broken |
| RC-3 | **MODERATE** | `cascor_service_adapter.py:68-72` | `get_current_metrics()` returns full ResponseEnvelope without unwrapping | Returns `{"status","data","meta"}` instead of metrics dict |
| RC-4 | **MODERATE** | `state_sync.py:57-65` | `sync()` reads `is_training`, `data.state`, `data.epoch`, `data.max_epochs` — all at wrong nesting levels in real cascor response | State hydration shows Stopped/epoch=0 even during active training |
| RC-5 | **SYSTEMIC** | `cascor-client/testing/fake_client.py` | FakeCascorClient response format diverges from real server in every method | All tests pass against fake but fail against real cascor |
| ISS-1 | **CRITICAL** | `service_backend.py:100-101` | `get_status()` returns cascor's nested structure (`state_machine`, `monitor`, `training_state`) but dashboard reads flat keys (`is_running`, `is_paused`, `phase`, `current_epoch`, `hidden_units`) | Status bar, phase display, epoch counter all show defaults |
| ISS-2 | **MODERATE** | `cascor_service_adapter.py:322-338` | `_CASCOR_TO_CANOPY_PARAM_MAP` has asymmetric reverse mapping: forward maps `nn_growth_convergence_threshold` → `patience` but reverse maps `patience` → `cn_training_convergence_threshold` | Param sync may apply to wrong canopy field |
| ISS-3 | **MODERATE** | Multiple files | Metric field names differ: real cascor uses `loss`, `accuracy`, `validation_loss`, `validation_accuracy`; dashboard expects `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy` | Metric values silently missing from plots |
| ISS-4 | **LOW** | `service_backend.py` / cascor API | Dataset endpoint returns metadata only (`train_samples`, `input_features`) but dashboard expects data arrays (`inputs`, `targets`) with different key names (`num_samples` vs `train_samples`) | Dataset visualization tab blank or incorrect |

### Refuted Claims (from original gap analysis)

| Claim | Status | Evidence |
|-------|--------|----------|
| Gap 1: `create_backend()` reads raw env vars instead of settings | **REFUTED** | `__init__.py:56-85` uses `get_settings()` first; raw env vars are legacy fallbacks only |
| Gap 2: `initialize()` never calls `CascorStateSync.sync()` | **REFUTED** | `service_backend.py:142` calls `CascorStateSync(self._adapter._client).sync()` when network exists |
| Gap 4: Discovery mutates `os.environ` but settings already cached | **REFUTED** | Discovery passes URL directly to `create_backend(service_url=discovered_url)`; no env mutation occurs |

---

## Architecture: Fix Strategy

### Chosen Approach: Canopy-Side Translation Layer (Option B)

All normalization is done in `CascorServiceAdapter`, which becomes the
single source of truth for translating cascor's native API responses into
canopy's internal format. This avoids breaking changes to the client library.

```
juniper-cascor (REST API)
  │ ResponseEnvelope: {"status":"success","data":...,"meta":...}
  ▼
juniper-cascor-client (JuniperCascorClient)
  │ Returns raw response.json() — no unwrapping (unchanged)
  ▼
CascorServiceAdapter (canopy — TRANSLATION LAYER)
  │ _unwrap_envelope() → strips status/data/meta
  │ _normalize_status() → flat dict matching DemoBackend format
  │ _normalize_metric() → canonical metric field names
  │ _normalize_metrics_history() → list of normalized metrics
  │ _normalize_topology() → graph-oriented format
  │ _normalize_dataset() → canopy key names
  ▼
ServiceBackend / _ServiceTrainingMonitor
  │ Consume normalized data (same shape as DemoBackend)
  ▼
main.py REST endpoints → Dashboard callbacks
  │ Dashboard reads flat keys: is_running, phase, train_loss, etc.
  ▼
Dashboard renders correctly
```

### Why Not Fix at Client Library Level (Option A)?

- Breaking API change for `JuniperCascorClient` — all consumers affected
- The client should remain a thin transport mirror of the real service
- Normalization is a UI-layer concern, not a transport concern
- Option B is lower risk and can ship without cross-repo coordination

---

## Phased Implementation Plan

### Phase 0: Characterization Tests

**Priority**: Prerequisite
**Scope**: juniper-canopy tests only
**Estimated time**: 45 min
**Depends on**: Nothing

Write characterization tests that capture the **current behavior** of the
service backend with real cascor response formats. These tests will initially
**fail** (documenting the bugs), then pass after fixes are applied.

#### Changes

1. **`src/tests/unit/test_response_normalization.py`** — **NEW**

   Create tests that feed real cascor ResponseEnvelope-formatted responses
   into `_ServiceTrainingMonitor` and `CascorServiceAdapter` methods, asserting
   the expected normalized output. Use a mock client that returns real-format
   responses.

   Test cases:
   - `test_get_recent_metrics_with_real_envelope` — feed `{"status":"success","data":[{...},{...}],"meta":{...}}`, expect list of metric dicts
   - `test_is_training_with_real_envelope` — feed nested `data.training_active: true`, expect `True`
   - `test_get_current_metrics_with_real_envelope` — feed envelope, expect inner `data` dict only
   - `test_get_status_returns_flat_dict` — feed nested cascor status, expect `is_running`, `phase`, `current_epoch` keys
   - `test_state_sync_with_real_envelope` — feed nested cascor status, expect correct `is_training`, `status`, `current_epoch`
   - `test_metrics_history_field_normalization` — feed `{"loss": 0.5, "accuracy": 0.8}`, expect `{"train_loss": 0.5, "train_accuracy": 0.8}`

2. **`src/tests/fixtures/cascor_response_fixtures.py`** — **NEW**

   Create reusable fixtures containing real cascor ResponseEnvelope-formatted
   responses for use across all test files. Include:
   - `real_training_status_response()` — nested `state_machine`, `monitor`, `training_state`
   - `real_metrics_history_response()` — `data` as flat list of metric dicts
   - `real_metrics_current_response()` — single metric in envelope
   - `real_training_params_response()` — flat param dict in envelope
   - `real_topology_response()` — weight-oriented format
   - `real_dataset_response()` — metadata-only format

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v
# Expected: tests FAIL (documenting current bugs)
```

---

### Phase 1: Adapter Normalization Layer

**Priority**: Critical — unblocks all dashboard display
**Scope**: `canopy/src/backend/cascor_service_adapter.py`
**Estimated time**: 1.5 hours
**Depends on**: Phase 0 (tests written, expected to fail)

Add normalization methods to `CascorServiceAdapter` and apply them throughout
`_ServiceTrainingMonitor`. This fixes RC-1, RC-2, RC-3, and ISS-3 in a single
coherent change.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Add normalization methods:

   ```python
   @staticmethod
   def _unwrap_envelope(response: Any) -> Any:
       """Strip ResponseEnvelope, returning the 'data' payload."""
       if isinstance(response, dict) and "data" in response and ("meta" in response or "status" in response):
           return response["data"]
       return response

   @staticmethod
   def _normalize_metric(item: dict) -> dict:
       """Normalize a single metric entry to canopy's expected field names."""
       return {
           "epoch": item.get("epoch", 0),
           "train_loss": item.get("train_loss") or item.get("loss"),
           "train_accuracy": item.get("train_accuracy") or item.get("accuracy"),
           "val_loss": item.get("val_loss") or item.get("validation_loss"),
           "val_accuracy": item.get("val_accuracy") or item.get("validation_accuracy"),
           "hidden_units": item.get("hidden_units", 0),
           "phase": item.get("phase"),
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
   ```

2. **`src/backend/cascor_service_adapter.py`** — Fix `_ServiceTrainingMonitor`:

   - `is_training` property (line 60-66):

     ```python
     @property
     def is_training(self) -> bool:
         try:
             status = self._client.get_training_status()
             data = CascorServiceAdapter._unwrap_envelope(status)
             if isinstance(data, dict):
                 return data.get("training_active", False) or data.get("monitor", {}).get("is_training", False)
             return status.get("is_training", False)
         except JuniperCascorClientError:
             return False
     ```

   - `get_current_metrics` (line 68-72):

     ```python
     def get_current_metrics(self) -> Dict[str, Any]:
         try:
             result = self._client.get_metrics()
             data = CascorServiceAdapter._unwrap_envelope(result)
             return CascorServiceAdapter._normalize_metric(data) if isinstance(data, dict) else data
         except JuniperCascorClientError:
             return {}
     ```

   - `get_recent_metrics` (line 74-79):

     ```python
     def get_recent_metrics(self, count: int = 100) -> list:
         try:
             result = self._client.get_metrics_history(count=count)
             return CascorServiceAdapter._normalize_metrics_history(result)
         except JuniperCascorClientError:
             return []
     ```

3. **`src/backend/cascor_service_adapter.py`** — Fix `is_training_in_progress` (line 282-284):

   Apply the same envelope unwrapping as `is_training` above. Both methods
   must use identical logic to prevent RC-2 from reappearing in the second
   code path.

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v -k "metrics or is_training or get_current"
# Expected: RC-1, RC-2, RC-3, ISS-3 tests now PASS
```

---

### Phase 2: ServiceBackend Status Normalization

**Priority**: Critical — unblocks status bar, epoch counter, phase display
**Scope**: `canopy/src/backend/service_backend.py`
**Estimated time**: 45 min
**Depends on**: Phase 1

Fix `ServiceBackend.get_status()` to translate cascor's nested status
structure into the flat dict format that the dashboard consumes. This
fixes ISS-1.

#### Changes

1. **`src/backend/service_backend.py`** — Replace `get_status()`:

   The current implementation (line 100-101) does:

   ```python
   def get_status(self) -> Dict[str, Any]:
       return self._adapter.get_training_status()
   ```

   Replace with a method that builds a flat dict matching `DemoBackend.get_status()`:

   ```python
   def get_status(self) -> Dict[str, Any]:
       raw = self._adapter.get_training_status()
       # raw is already unwrapped by _unwrap_response in the adapter
       sm = raw.get("state_machine", {}) if isinstance(raw, dict) else {}
       monitor = raw.get("monitor", {}) if isinstance(raw, dict) else {}
       ts = raw.get("training_state", {}) if isinstance(raw, dict) else {}

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
           "current_epoch": (
               monitor.get("current_epoch")
               or monitor.get("epoch")
               or ts.get("current_epoch")
               or ts.get("epoch")
               or 0
           ),
           "hidden_units": (
               monitor.get("current_hidden_units")
               or monitor.get("hidden_units")
               or 0
           ),
           "network_connected": raw.get("network_loaded", False),
           "monitoring_active": True,
       }
   ```

   This mapping is derived from the actual cascor `lifecycle.get_status()`
   response structure (verified in `cascor/src/api/lifecycle/manager.py`
   lines 450-462) and the dashboard's expected keys (verified in
   `dashboard_manager.py` lines 1525-1532).

#### Dashboard Key Mapping Reference

| Dashboard Key | Cascor Source Path | DemoBackend Equivalent |
|---------------|-------------------|----------------------|
| `is_running` | `state_machine.status == "STARTED"` | `self._fsm.status == "STARTED"` |
| `is_paused` | `state_machine.status == "PAUSED"` | `self._fsm.status == "PAUSED"` |
| `completed` | `state_machine.status == "COMPLETED"` | `self._fsm.status == "COMPLETED"` |
| `failed` | `state_machine.status == "FAILED"` | `self._fsm.status == "FAILED"` |
| `phase` | `state_machine.phase` | `self._training_phase` |
| `current_epoch` | `monitor.current_epoch` | `self._current_epoch` |
| `hidden_units` | `monitor.current_hidden_units` | `self._hidden_units` |
| `is_training` | `training_active` | `self._is_training` |
| `network_connected` | `network_loaded` | `self._network is not None` |

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_response_normalization.py -v -k "get_status"
pytest tests/unit/test_service_backend.py -v
```

---

### Phase 3: CascorStateSync Fix

**Priority**: Critical — unblocks correct initial state hydration
**Scope**: `canopy/src/backend/state_sync.py`
**Estimated time**: 45 min
**Depends on**: Phase 1 (uses normalization methods)

Fix `CascorStateSync.sync()` to correctly navigate real cascor's nested
response structure. This fixes RC-4.

#### Design Decision: Use Adapter, Not Raw Client

The current `CascorStateSync` is instantiated with a raw `_client` reference
and reads responses directly. This duplicates envelope/nesting logic that now
lives in the adapter. The fix has two options:

- **Option A (minimal)**: Fix the field navigation in `state_sync.py` directly
- **Option B (cleaner)**: Refactor `CascorStateSync` to use adapter methods
  instead of raw client calls

**Recommended: Option A for this phase**, with a note to refactor in a future
cleanup pass. This minimizes the blast radius and keeps the fix focused.

#### Changes

1. **`src/backend/state_sync.py`** — Fix `sync()` method (lines 57-65):

   Current code reads wrong nesting:

   ```python
   state.is_training = status_response.get("is_training", False)
   data = status_response.get("data", {})
   raw_state = data.get("state", "idle")
   state.current_epoch = data.get("epoch", 0)
   state.max_epochs = data.get("max_epochs", 0)
   ```

   Fix to navigate real cascor structure:

   ```python
   # Unwrap ResponseEnvelope
   data = status_response.get("data", status_response)
   if not isinstance(data, dict):
       data = {}

   # Extract training active flag
   state.is_training = (
       status_response.get("is_training")  # FakeCascorClient compat
       or data.get("training_active", False)
   )

   # Extract state string
   sm = data.get("state_machine", {})
   raw_state = (
       data.get("state")  # FakeCascorClient: data.state
       or (sm.get("current_state", "").lower() if isinstance(sm, dict) else None)
       or (sm.get("status", "").lower() if isinstance(sm, dict) else None)
       or "idle"
   )
   state.status = self._normalize_status(raw_state)

   # Extract epoch
   monitor = data.get("monitor", {})
   ts = data.get("training_state", {})
   state.current_epoch = (
       data.get("epoch")  # FakeCascorClient
       or (monitor.get("current_epoch") if isinstance(monitor, dict) else None)
       or (monitor.get("epoch") if isinstance(monitor, dict) else None)
       or (ts.get("current_epoch") if isinstance(ts, dict) else None)
       or 0
   )

   # Extract max epochs
   state.max_epochs = (
       data.get("max_epochs")  # FakeCascorClient
       or (ts.get("max_epochs") if isinstance(ts, dict) else None)
       or (ts.get("epochs_max") if isinstance(ts, dict) else None)
       or 0
   )
   ```

2. **`src/backend/state_sync.py`** — Fix metrics history parsing (line ~89-93):

   Current code:

   ```python
   state.metrics_history = history_response.get("data", {}).get("history", [])
   ```

   Fix:

   ```python
   data = history_response.get("data", history_response)
   if isinstance(data, list):
       state.metrics_history = data  # Real server: data is the list
   elif isinstance(data, dict):
       state.metrics_history = data.get("history", [])  # FakeCascorClient
   else:
       state.metrics_history = []
   ```

3. **`src/backend/state_sync.py`** — Fix `_normalize_status()`:

   Ensure it handles real cascor's uppercase state names:
   - `"started"` / `"STARTED"` → `"Started"`
   - `"paused"` / `"PAUSED"` → `"Paused"`
   - `"completed"` / `"COMPLETED"` → `"Completed"`
   - `"failed"` / `"FAILED"` → `"Failed"`
   - `"idle"` / `"IDLE"` → `"Stopped"`
   - `"training"` → `"Started"` (FakeCascorClient compat)

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_state_sync.py -v
pytest tests/unit/test_response_normalization.py -v -k "state_sync"
```

---

### Phase 4: Parameter Map Cleanup

**Priority**: Important — prevents param sync errors
**Scope**: `canopy/src/backend/cascor_service_adapter.py`
**Estimated time**: 20 min
**Depends on**: Phase 1

Fix the asymmetric `_CASCOR_TO_CANOPY_PARAM_MAP` by generating the reverse
map from the forward map. This fixes ISS-2.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Fix param maps:

   Current forward map (lines 322-330):

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
   ```

   Current reverse map (lines 332-338) has asymmetry where `patience` maps
   to `cn_training_convergence_threshold` instead of `nn_growth_convergence_threshold`.

   Fix: **Generate reverse map from forward map:**

   ```python
   _CASCOR_TO_CANOPY_PARAM_MAP = {v: k for k, v in _CANOPY_TO_CASCOR_PARAM_MAP.items()}
   ```

   This produces a consistent mapping:
   - `learning_rate` → `nn_learning_rate`
   - `max_hidden_units` → `nn_max_hidden_units`
   - `epochs_max` → `nn_max_total_epochs`
   - `patience` → `nn_growth_convergence_threshold`
   - `candidate_pool_size` → `cn_pool_size`
   - `correlation_threshold` → `cn_correlation_threshold`
   - `candidate_epochs` → `cn_training_iterations`

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/test_service_controls.py -v
pytest tests/integration/test_param_apply_roundtrip.py -v
```

---

### Phase 5: FakeCascorClient Alignment

**Priority**: Important — prevents future divergence, makes tests reliable
**Scope**: `juniper-cascor-client/juniper_cascor_client/testing/fake_client.py`
**Estimated time**: 1.5 hours
**Depends on**: Phases 1-4 (production fixes stable first)

Update `FakeCascorClient` to match the real cascor server's `ResponseEnvelope`
format. This fixes RC-5 at the systemic level.

#### Changes

1. **`fake_client.py`** — Update all response methods to use `ResponseEnvelope`
   format:

   | Change | Before | After |
   |--------|--------|-------|
   | Status string | `"status": "ok"` | `"status": "success"` |
   | Meta field | absent | `"meta": {"timestamp": ..., "version": "..."}` |
   | `get_training_status()` | `is_training` at top level; `data.state` flat | `data.training_active`; `data.state_machine`, `data.monitor`, `data.training_state` nested |
   | `get_metrics_history()` | `data: {"history": [...], "total": N}` | `data: [... list of metrics ...]` |
   | `get_metrics()` | `data: {"epoch":..., "train_loss":...}` | `data: {"epoch":..., "loss":..., "accuracy":...}` (real field names) |
   | `get_training_params()` | `data: {"params": {...}, "epochs":...}` | `data: {"learning_rate":..., "max_hidden_units":..., ...}` (flat) |
   | `get_topology()` | Graph-oriented (layers/nodes/connections) | Weight-oriented (hidden_units array, output_weights) |

2. **Add helper method** to fake client for consistency:

   ```python
   def _success_response(self, data: Any) -> dict:
       return {
           "status": "success",
           "data": data,
           "meta": {"timestamp": time.time(), "version": "0.4.0-fake"},
       }
   ```

#### Impact on Existing Tests

This change will break **many existing tests** that assert against the old
fake response format. Each test file must be updated:

| Test File | Expected Breakage | Fix |
|-----------|------------------|-----|
| `test_cascor_service_adapter.py` | Mock response formats | Update mock returns to new format |
| `test_state_sync.py` | Status response assertions | Update expected data paths |
| `test_fake_service_backend.py` | Full-chain assertions | Update expected response shapes |
| `test_service_controls.py` | Control response assertions | Update expected message format |
| `test_external_cascor_attach.py` | Attach response assertions | Update expected data paths |
| `test_training_controls_service_mode.py` | Control responses | Update assertion keys |

#### Strategy for Test Updates

1. Update `FakeCascorClient` response format
2. Run full test suite — collect all failures
3. Fix each test to work with new response format
4. Verify all tests pass
5. Run characterization tests from Phase 0 to confirm they also pass

#### Verification

```bash
# In juniper-cascor-client repo:
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v

# In juniper-canopy repo:
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ -v
```

---

### Phase 6: Dataset and Topology Adapters

**Priority**: Low — polish for complete dashboard functionality
**Scope**: `canopy/src/backend/cascor_service_adapter.py`, `service_backend.py`
**Estimated time**: 1 hour
**Depends on**: Phase 1

Fix dataset and topology format translation. This fixes ISS-4 partially.

#### Changes

1. **`src/backend/cascor_service_adapter.py`** — Add dataset normalization:

   Map cascor metadata keys to canopy's expected format:

   ```python
   @staticmethod
   def _normalize_dataset(data: dict) -> dict:
       """Normalize cascor dataset metadata to canopy format."""
       return {
           "loaded": data.get("loaded", False),
           "num_samples": data.get("train_samples", 0),
           "num_features": data.get("input_features", 0),
           "num_classes": data.get("output_features", 0),
           "train_samples": data.get("train_samples", 0),
           "test_samples": data.get("test_samples", 0),
           "input_features": data.get("input_features", 0),
           "output_features": data.get("output_features", 0),
       }
   ```

2. **`src/backend/service_backend.py`** — Apply dataset normalization in
   `get_dataset()`.

3. **Topology**: Verify that `extract_network_topology()` already handles
   format translation. The adapter has existing topology extraction logic
   that may already handle the weight-oriented format. If not, add a
   `_normalize_topology()` method.

#### Known Limitation

Real cascor's dataset endpoint returns **metadata only** — no raw data
arrays (`inputs`, `targets`). The dataset scatter plot requires these arrays.
Options:

- **Option A**: Fetch dataset from juniper-data-client directly (if data
  service is available)
- **Option B**: Add a dataset retrieval endpoint to cascor (requires cascor
  change — out of scope for this plan)
- **Option C**: Show metadata-only view in service mode with a message
  indicating data arrays are not available

**Recommendation**: Option C for now. Document the limitation and add a
future task for Option A or B.

#### Verification

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ -v -k "dataset or topology"
```

---

### Phase 7: Integration Validation & Regression Testing

**Priority**: Critical — confirms all fixes work end-to-end
**Scope**: juniper-canopy tests, manual E2E validation
**Estimated time**: 1.5 hours
**Depends on**: Phases 1-6

#### Automated Tests

1. **Run full canopy test suite** (demo mode, no cascor needed):

   ```bash
   cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
   pytest tests/ -v --tb=short
   ```

2. **Run characterization tests** (Phase 0 tests should now all pass):

   ```bash
   pytest tests/unit/test_response_normalization.py -v
   ```

3. **Run canopy test suite with coverage**:

   ```bash
   pytest tests/ --cov=. --cov-report=term-missing
   ```

4. **Run cascor regression tests** (verify no upstream breakage):

   ```bash
   cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
   conda activate JuniperCascor
   bash scripts/run_tests.bash
   ```

5. **Run cascor-client tests** (if FakeCascorClient was updated):

   ```bash
   cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
   pytest tests/ -v
   ```

#### Manual E2E Validation

```bash
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# Terminal 2: Start canopy (should auto-discover cascor)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: Verify endpoints return correct data
curl -s http://localhost:8050/api/status | python -m json.tool
curl -s http://localhost:8050/api/metrics/history?limit=10 | python -m json.tool
curl -s http://localhost:8050/api/metrics | python -m json.tool
curl -s http://localhost:8050/api/topology | python -m json.tool
curl -s http://localhost:8050/api/dataset | python -m json.tool
```

#### Visual Verification Checklist

- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Hidden units count updates on cascade events
- [ ] Loss chart plots live data with descending curve
- [ ] Accuracy chart plots live data with ascending curve
- [ ] Network topology renders with correct structure
- [ ] Phase indicator shows correct training phase (output/candidate)
- [ ] Parameter panel shows actual cascor parameters
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and state restores

---

## Dependency Graph

```
Phase 0 (characterization tests)
    └──→ Phase 1 (adapter normalization — RC-1, RC-2, RC-3, ISS-3)
              ├──→ Phase 2 (status normalization — ISS-1)
              ├──→ Phase 3 (state sync fix — RC-4)
              ├──→ Phase 4 (param map cleanup — ISS-2)
              └──→ Phase 6 (dataset/topology adapters — ISS-4)
                        │
              ┌─────────┘
              ▼
         Phase 5 (FakeCascorClient alignment — RC-5)
              └──→ Phase 7 (integration validation)
```

Phases 2, 3, 4, and 6 can be done **in parallel** after Phase 1.
Phase 5 should be done **after** all production fixes are stable.
Phase 7 is the final validation gate.

---

## Files Modified Summary

### juniper-canopy (primary changes)

| File | Phase | Changes |
|------|-------|---------|
| `src/backend/cascor_service_adapter.py` | 1, 4 | Add normalization methods; fix `_ServiceTrainingMonitor`; fix `is_training_in_progress`; fix param map |
| `src/backend/service_backend.py` | 2 | Replace `get_status()` with flat-dict builder |
| `src/backend/state_sync.py` | 3 | Fix field navigation for real cascor response structure |
| `src/tests/unit/test_response_normalization.py` | 0 | **NEW** — Characterization tests for real response formats |
| `src/tests/fixtures/cascor_response_fixtures.py` | 0 | **NEW** — Reusable real-format response fixtures |

### juniper-canopy (test updates for Phase 5)

| File | Phase | Changes |
|------|-------|---------|
| `src/tests/unit/test_cascor_service_adapter.py` | 5 | Update mock response formats |
| `src/tests/unit/test_state_sync.py` | 5 | Update expected data paths |
| `src/tests/unit/test_service_backend.py` | 5 | Update status response assertions |
| `src/tests/integration/test_fake_service_backend.py` | 5 | Update full-chain assertions |
| `src/tests/integration/test_external_cascor_attach.py` | 5 | Update attach response assertions |
| `src/tests/integration/test_training_controls_service_mode.py` | 5 | Update control response assertions |

### juniper-cascor-client (Phase 5 only)

| File | Phase | Changes |
|------|-------|---------|
| `juniper_cascor_client/testing/fake_client.py` | 5 | Align response format with real ResponseEnvelope |

### No Changes Required

| Repo | Reason |
|------|--------|
| juniper-cascor | Server API already exposes all necessary endpoints correctly |
| juniper-cascor-client (client.py) | Client correctly returns raw responses; normalization is canopy's responsibility |

---

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| FakeCascorClient update breaks many tests | Test suite fails until tests updated | **High** | Do Phase 5 as a single atomic pass; run full suite before committing |
| Status normalization misses a state value | Dashboard shows wrong status for edge case | Medium | Exhaustive state mapping table; test each FSM state |
| Metric field normalization drops a field | Chart shows gaps | Medium | Normalize with fallback chain (`train_loss` OR `loss`); test with both formats |
| Topology format not fully compatible | Network visualizer renders incorrectly | Low | Manual visual verification in Phase 7 |
| Dataset arrays still missing in service mode | Dataset tab blank | **Expected** | Document as known limitation; plan future fix |
| `is_training_in_progress()` not updated | RC-2 reappears in second code path | Medium | Fix **both** methods in Phase 1; add test for both |
| Normalization logic drifts from cascor API | Future cascor changes break canopy | Low | Centralize in one file; add contract tests |

---

## Success Criteria

### Must Pass (Phase 7 gate)

- [ ] All characterization tests pass (Phase 0 tests)
- [ ] Full canopy test suite passes with zero failures
- [ ] Full cascor test suite passes with zero regressions
- [ ] `curl /api/status` returns flat dict with `is_running`, `phase`, `current_epoch`
- [ ] `curl /api/metrics/history` returns non-empty `{"history": [...]}` during training
- [ ] `curl /api/metrics` returns unwrapped metric dict
- [ ] Dashboard status bar shows correct state
- [ ] Dashboard metrics charts plot data

### Should Pass (desirable)

- [ ] Parameter panel shows actual cascor params
- [ ] Parameter changes from canopy apply to cascor
- [ ] Network topology renders correctly
- [ ] State sync correctly hydrates on connect

### Known Limitations (acceptable)

- [ ] Dataset visualization tab may show metadata only (no scatter plot) in
  service mode due to missing raw data endpoint in cascor
- [ ] WebSocket relay pushes metrics but Dash callbacks don't consume them
  (polling is sole data path — pre-existing architectural limitation)

---

## Future Work (Out of Scope)

These items are identified but **not addressed** in this plan:

1. **Dataset data endpoint** — Add a cascor endpoint to serve raw training
   data arrays, or fetch from juniper-data-client directly
2. **WebSocket-driven metrics** — Wire Dash callbacks to consume WebSocket
   message buffer for real-time push updates instead of HTTP polling
3. **Typed response models** — Define shared canonical models (`TrainingStatus`,
   `MetricPoint`, `TopologyGraph`) usable by both canopy and client library
4. **Client library normalization API** — Add optional `NormalizedCascorClient`
   wrapper or `unwrap_data()` helper to client library (non-breaking)
5. **Refactor CascorStateSync** — Use adapter methods instead of raw client
   calls to eliminate duplicated envelope handling logic
6. **BackendProtocol response contracts** — Define expected response shapes
   explicitly in the protocol, not just return types, to prevent backend
   shape divergence
