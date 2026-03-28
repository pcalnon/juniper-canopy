# Canopy → External CasCor Connection: Development Plan

**Version**: 1.0.0
**Date**: 2026-03-25
**Author**: Amp (AI Agent)
**Status**: Approved — Ready for Implementation

---

## Executive Summary

This plan addresses the critical use case of connecting juniper-canopy to an
externally running juniper-cascor instance as a temporary monitoring and
management frontend. Analysis reveals that the core infrastructure is
**largely already built** across the three codebases (juniper-canopy,
juniper-cascor, juniper-cascor-client). The remaining work is primarily
**integration wiring, state hydration, and consistency fixes** rather than
new architecture.

**Estimated effort**: Medium (4–8 hours across all phases)

---

## Requirements Traceability

| #  | Requirement                                  | Status     | Gaps                                               |
|----|----------------------------------------------|------------|----------------------------------------------------|
| 1  | Auto-detect running cascor on startup        | ✅ Built   | Discovery → backend selection has env var mismatch |
| 2  | Connect to discovered cascor                 | ✅ Built   | `attach_to_existing()` is non-destructive          |
| 3  | Connection must not reset cascor params      | ✅ Built   | Attach only calls `get_network()` (read-only)      |
| 4  | Retrieve metrics from cascor                 | ✅ Built   | Metrics relay streams via WebSocket                |
| 5  | Display retrieved metrics                    | ⚠️ Partial | Initial metrics history not hydrated on connect    |
| 6  | Retrieve training parameters                 | ⚠️ Partial | `CascorStateSync` exists but is never called       |
| 7  | Display retrieved parameters                 | ⚠️ Partial | `/api/state` returns defaults in service mode      |
| 8  | Apply param changes to running cascor        | ⚠️ Partial | Parameter map incomplete (4 of ~7 params mapped)   |
| 9  | Monitoring/visualization reflects live state | ⚠️ Partial | No topology fetch on cascade_add events            |
| 10 | Training controls functional                 | ✅ Built   | All controls delegate to cascor REST API           |
| 11 | Canopy shutdown doesn't affect cascor        | ✅ Built   | `shutdown()` only closes HTTP session              |
| 12 | Canopy can start/stop multiple times         | ✅ Built   | Each process creates fresh client/backend          |

---

## Architecture Overview

```bash
┌──────────────────────────────────────────────────────────┐
│                    juniper-canopy                        │
│                                                          │
│  main.py (lifespan)                                      │
│    ├── discover_cascor()  ← probes localhost:8200        │
│    ├── create_backend()   ← selects ServiceBackend       │
│    └── backend.initialize()                              │
│          ├── adapter.connect()        ← health check     │
│          ├── adapter.attach_to_existing() ← non-destruct │
│          ├── CascorStateSync.sync()   ← [NEW] hydrate    │
│          └── adapter.start_metrics_relay() ← WS stream   │
│                                                          │
│  ServiceBackend ──→ CascorServiceAdapter                 │
│                       ├── JuniperCascorClient (REST)     │
│                       └── CascorTrainingStream (WS)      │
└──────────────────────────────────────────────────────────┘
           │ REST/WS │
           ▼         ▼
┌──────────────────────────────────────────────────────────┐
│                   juniper-cascor                         │
│                                                          │
│  FastAPI API Server (port 8200)                          │
│    ├── /v1/training/* — training control                 │
│    ├── /v1/metrics/* — metrics retrieval                 │
│    ├── /v1/network/* — network topology/stats            │
│    ├── /v1/dataset — dataset metadata                    │
│    ├── /v1/decision-boundary — visualization data        │
│    ├── /ws/training — real-time metrics stream           │
│    └── /ws/control — bidirectional control               │
│                                                          │
│  TrainingLifecycleManager                                │
│    └── CascadeCorrelationNetwork (running independently) │
└──────────────────────────────────────────────────────────┘
```

---

## Identified Gaps (Prioritized)

### Priority 1 — Critical (blocks core requirements)

#### Gap 1: Backend factory ignores new settings system

**File**: `canopy/src/backend/__init__.py`
**Issue**: `create_backend()` reads raw `CASCOR_DEMO_MODE` and `CASCOR_SERVICE_URL`
env vars, but the application uses `JUNIPER_CANOPY_*` prefixed settings via Pydantic.
If the user configures via the new env prefix, the factory may select the wrong backend.
**Fix**: Make `create_backend()` accept settings or use `get_settings()` internally.

#### Gap 2: State not hydrated on service connect

**File**: `canopy/src/backend/service_backend.py`
**Issue**: `ServiceBackend.initialize()` attaches to cascor but never calls
`CascorStateSync.sync()`. The dashboard starts with blank/default values instead
of the actual cascor state.
**Fix**: Call `CascorStateSync` after attach, update `training_state` and seed
dashboard with initial metrics/topology.

#### Gap 3: `/api/state` returns defaults in service mode

**File**: `canopy/src/main.py` (line ~569)
**Issue**: The `/api/state` endpoint has detailed nn_*/cn_* param extraction for
demo mode but falls through to bare `training_state.get_state()` for service mode,
which only has the basic fields.
**Fix**: In service mode, fetch params from cascor via the adapter and map to
canopy's nn_*/cn_* namespace.

#### Gap 4: Auto-discovery env var mutation doesn't update settings

**File**: `canopy/src/main.py` (line ~147)
**Issue**: After discovery, the code sets `os.environ["CASCOR_SERVICE_URL"]` but
`settings` was already loaded (and cached via `@lru_cache`). Later references to
`settings.cascor_service_url` still return None.
**Fix**: Pass discovered URL directly to `create_backend()` or clear/rebuild
settings cache after discovery.

### Priority 2 — Important (affects user experience)

#### Gap 5: Parameter mapping incomplete

**File**: `canopy/src/backend/cascor_service_adapter.py`
**Issue**: `_CANOPY_TO_CASCOR_PARAM_MAP` only maps 4 params:
`nn_learning_rate`, `nn_max_hidden_units`, `cn_pool_size`, `cn_correlation_threshold`.
Missing: `nn_max_total_epochs` → `epochs_max`, `nn_growth_convergence_threshold` →
`patience`, and others.
**Fix**: Complete the mapping and add reverse mapping for state sync.

#### Gap 6: No topology refresh on cascade events

**File**: `canopy/src/backend/cascor_service_adapter.py`
**Issue**: The metrics relay forwards messages but doesn't trigger a topology
refresh when a `cascade_add` event arrives. The network visualizer shows stale
topology until the page is refreshed.
**Fix**: On `cascade_add` message, fetch fresh topology from cascor and broadcast
as a `topology` message.

#### Gap 7: Response normalization inconsistent

**File**: `canopy/src/backend/cascor_service_adapter.py`
**Issue**: Some methods unwrap `response["data"]` (e.g., `get_decision_boundary`),
others return raw responses (e.g., `get_training_status`, `get_dataset_info`).
This causes inconsistent data shapes in the UI.
**Fix**: Add consistent response unwrapping for all service adapter methods.

### Priority 3 — Minor (polish and robustness)

#### Gap 8: Local training_state drifts from cascor reality

**File**: `canopy/src/main.py`
**Issue**: In service mode, `training_state` is only updated when canopy
itself calls control operations. If cascor's state changes externally (e.g.,
training completes), canopy's local state doesn't update until next poll.
**Fix**: Update `training_state` from incoming WebSocket state messages in
the metrics relay.

#### Gap 9: Auth env var potentially miswired

**File**: `canopy/src/backend/__init__.py` (line 59)
**Issue**: `api_key = os.getenv("JUNIPER_DATA_API_KEY")` is used for cascor
service connection. CasCor and JuniperData may use different API keys.
**Fix**: Use `JUNIPER_CASCOR_API_KEY` (consistent with juniper-cascor-client).

---

## Phased Implementation Plan

### Phase 1: Backend Selection & Discovery Fix

**Priority**: Critical
**Scope**: canopy only
**Estimated time**: 30 min

#### Changes

1. **`canopy/src/backend/__init__.py`** — Update `create_backend()`:
   - Accept optional `service_url` and `demo_mode` parameters
   - Fall back to `get_settings()` values instead of raw env vars
   - Use `JUNIPER_CASCOR_API_KEY` for auth

2. **`canopy/src/main.py`** — Update lifespan discovery flow:
   - Pass discovered URL directly to `create_backend(service_url=discovered_url)`
   - Remove `os.environ["CASCOR_SERVICE_URL"]` mutation
   - Store discovered URL on settings or app state for later reference

#### Tests

- `test_backend_factory.py` — verify factory respects settings-based config
- `test_cascor_discovery.py` — verify discovery URL flows to backend creation

---

### Phase 2: State Hydration on Connect

**Priority**: Critical
**Scope**: canopy only
**Estimated time**: 1 hour

#### Changes

1. **`canopy/src/backend/service_backend.py`** — Update `initialize()`:
   - After successful attach, instantiate `CascorStateSync` with the client
   - Call `sync()` to fetch training status, params, topology, metrics history
   - Return `SyncedState` to caller for app-level state population

2. **`canopy/src/main.py`** — Update lifespan to consume synced state:
   - After `backend.initialize()`, if service mode, populate `training_state`
     with synced values (status, epoch, learning_rate, max_hidden_units, etc.)
   - Log synced state summary

3. **`canopy/src/backend/state_sync.py`** — Minor fixes:
   - Ensure response unwrapping is consistent with cascor API format
   - Add param name normalization (cascor names → canopy nn_*/cn_* names)

#### Tests

- `test_state_sync.py` — verify sync fetches all state components
- `test_service_backend.py` — verify initialize calls sync
- New: `test_state_hydration_integration.py` — verify full startup populates state

---

### Phase 3: Service-Mode `/api/state` Endpoint

**Priority**: Critical
**Scope**: canopy only
**Estimated time**: 45 min

#### Changes

1. **`canopy/src/main.py`** — Update `/api/state` endpoint:
   - In service mode, fetch params from `backend._adapter._client.get_training_params()`
   - Map cascor param names to canopy's nn_*/cn_* namespace
   - Merge with `training_state.get_state()` for display

2. **`canopy/src/backend/cascor_service_adapter.py`** — Add reverse param mapping:
   - Define `_CASCOR_TO_CANOPY_PARAM_MAP` (reverse of existing map)
   - Add `get_canopy_params()` method that returns params in canopy namespace

#### Tests

- `test_api_state_endpoint.py` — verify service mode returns nn_*/cn_* params
- `test_cascor_api_compatibility.py` — verify param format consistency

---

### Phase 4: Complete Parameter Mapping

**Priority**: Important
**Scope**: canopy only
**Estimated time**: 30 min

#### Changes

1. **`canopy/src/backend/cascor_service_adapter.py`** — Complete param maps:
   - Forward map (canopy → cascor): add missing params
     - `nn_max_total_epochs` → `epochs_max`
     - `cn_training_convergence_threshold` → `patience`
     - `cn_training_iterations` → `candidate_epochs`
   - Reverse map (cascor → canopy): full reverse mapping
     - `learning_rate` → `nn_learning_rate`
     - `max_hidden_units` → `nn_max_hidden_units`
     - `epochs_max` → `nn_max_total_epochs`
     - `candidate_pool_size` → `cn_pool_size`
     - `correlation_threshold` → `cn_correlation_threshold`
     - `patience` → `cn_training_convergence_threshold`

#### Tests

- `test_service_controls.py` — verify all params round-trip correctly
- New param mapping unit tests

---

### Phase 5: Topology Refresh & Response Normalization

**Priority**: Important
**Scope**: canopy only
**Estimated time**: 1 hour

#### Changes

1. **`canopy/src/backend/cascor_service_adapter.py`** — Metrics relay enhancement:
   - On `cascade_add` message, fetch fresh topology via REST
   - Broadcast topology as a `topology` message to dashboard
   - Add `_unwrap_response()` helper for consistent response normalization
   - Apply to all service adapter methods

2. **`canopy/src/backend/cascor_service_adapter.py`** — Normalize responses:
   - `get_training_status()` — unwrap `data` key if present
   - `get_network_data()` — unwrap `data` key
   - `get_dataset_info()` — unwrap `data` key

#### Tests

- `test_non_destructive_connection.py` — verify topology refresh on cascade event
- `test_service_backend.py` — verify normalized response shapes

---

### Phase 6: Live State Synchronization

**Priority**: Important
**Scope**: canopy only
**Estimated time**: 45 min

#### Changes

1. **`canopy/src/backend/cascor_service_adapter.py`** — Update relay loop:
   - On `state` messages, update canopy's `training_state` via callback
   - On `event` messages (training_complete), update status

2. **`canopy/src/backend/service_backend.py`** — Add state callback:
   - Accept a `state_update_callback` parameter
   - Pass to adapter for relay-driven state updates

3. **`canopy/src/main.py`** — Wire state callback in lifespan:
   - Pass `training_state.update_state` as callback to service backend

#### Tests

- `test_websocket_state.py` — verify state updates propagate
- New: `test_live_state_sync.py` — verify training_state updates from relay

---

### Phase 7: Regression Testing & Validation

**Priority**: Critical
**Scope**: Both canopy and cascor
**Estimated time**: 1.5 hours

#### New Tests

1. **`test_external_cascor_attach.py`** (integration):
   - Verify non-destructive attach to running cascor
   - Verify no `create_network` or `reset` calls made
   - Verify params/epoch/status populate correctly

2. **`test_canopy_restart_during_training.py`** (integration):
   - Start canopy → verify cascor training continues
   - Stop canopy → verify cascor keeps running
   - Restart canopy → verify reattach and state restore

3. **`test_param_apply_roundtrip.py`** (integration):
   - Apply each mappable param from canopy
   - Verify cascor received the update
   - Verify UI reflects new values

4. **`test_training_controls_service_mode.py`** (integration):
   - Pause/resume/stop from canopy
   - Verify cascor state changes
   - Verify canopy state stays aligned

#### Existing Test Validation

- Run full canopy test suite: `cd src && pytest tests/ -v`
- Run full cascor test suite: `cd src/tests && bash scripts/run_tests.bash`
- Ensure no regressions in demo mode

---

## Dependency Order

```bash
Phase 1 (backend selection)
    └──→ Phase 2 (state hydration)
              ├──→ Phase 3 (/api/state fix)
              └──→ Phase 4 (param mapping)
                        └──→ Phase 5 (topology + normalization)
                                  └──→ Phase 6 (live state sync)
                                            └──→ Phase 7 (testing)
```

Phases 3 and 4 can be done in parallel after Phase 2.
Phases 5 and 6 can be done in parallel after Phase 4.

---

## Files Modified (Summary)

### juniper-canopy

| File                                                           | Changes                                                                       |
|----------------------------------------------------------------|-------------------------------------------------------------------------------|
| `src/backend/__init__.py`                                      | Accept settings, fix auth env var                                             |
| `src/backend/service_backend.py`                               | Add state sync on initialize, state callback                                  |
| `src/backend/cascor_service_adapter.py`                        | Complete param maps, response normalization, topology refresh, state callback |
| `src/backend/state_sync.py`                                    | Param name normalization, response unwrapping                                 |
| `src/main.py`                                                  | Discovery flow fix, state hydration, /api/state service mode                  |
| `src/tests/unit/test_backend_factory.py`                       | Settings-based backend selection                                              |
| `src/tests/unit/test_state_sync.py`                            | Verify sync completeness                                                      |
| `src/tests/unit/test_service_backend.py`                       | Initialize calls sync                                                         |
| `src/tests/integration/test_api_state_endpoint.py`             | Service mode params                                                           |
| `src/tests/integration/test_external_cascor_attach.py`         | **NEW**                                                                       |
| `src/tests/integration/test_canopy_restart_during_training.py` | **NEW**                                                                       |
| `src/tests/integration/test_param_apply_roundtrip.py`          | **NEW**                                                                       |
| `src/tests/integration/test_training_controls_service_mode.py` | **NEW**                                                                       |

### juniper-cascor

No changes required. The cascor API already exposes all necessary endpoints.
Verify via existing test suite that no regressions are introduced.

### juniper-cascor-client

No changes required. The client already wraps all needed API calls.

---

## Verification Commands

```bash
# Phase 1-6: Run canopy unit tests (demo mode, no cascor needed)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/unit/ -v

# Phase 7: Run canopy integration tests
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/integration/ -v

# Verify cascor has no regressions
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
bash scripts/run_tests.bash

# Full canopy suite with coverage
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ --cov=. --cov-report=term-missing

# End-to-end verification (requires both services running)
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
python server.py

# Terminal 2: Start canopy (should auto-discover cascor)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
uvicorn main:app --host 0.0.0.0 --port 8050
```

---

## Risk Mitigation

| Risk                                | Impact                            | Mitigation                                                                      |
|-------------------------------------|-----------------------------------|---------------------------------------------------------------------------------|
| State sync response format mismatch | Dashboard shows wrong data        | Add response normalization + comprehensive fixtures                             |
| Parameter mapping misalignment      | Params don't apply correctly      | Validate via round-trip integration tests                                       |
| WebSocket relay message loss        | Missing metrics in dashboard      | Existing exponential backoff reconnection handles this                          |
| Cascor treats WS disconnect as stop | Training stops on canopy shutdown | Verify cascor server behavior in test — current code shows cascor does not stop |
| Demo mode regression                | Existing tests break              | Run full test suite with `CASCOR_DEMO_MODE=1` before and after                  |

---

## Success Criteria

- [ ] Canopy auto-discovers running cascor and enters service mode
- [ ] Dashboard displays current cascor state immediately on connect
- [ ] Parameters panel shows actual cascor params (not defaults)
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Network topology updates on cascade events
- [ ] Training controls (start/stop/pause/resume/reset) work
- [ ] Stopping canopy does not affect cascor training
- [ ] Restarting canopy reconnects and restores state
- [ ] All existing demo-mode tests continue to pass
- [ ] No regressions in cascor test suite
