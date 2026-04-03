# Juniper Project: Regression Development Roadmap

**Date**: 2026-04-02
**Companion Documents**:

- `REGRESSION_ANALYSIS_2026-04-02.md`
- `REGRESSION_REMEDIATION_PLAN_2026-04-02.md`
**Status**: Active

---

## Roadmap Overview

| Phase   | Priority      | Scope                    | Tasks         | Est. Complexity |
|---------|---------------|--------------------------|---------------|-----------------|
| Phase 1 | P0 — Critical | CasCor Training Failure  | 7             | High            |
| Phase 2 | P0 — Critical | Canopy-CasCor Connection | 2             | Low             |
| Phase 3 | P1 — High     | Canopy UI Fixes          | 11            | Medium          |
| Phase 4 | P2 — Medium   | Dark Mode Styling        | 3             | Low             |
| Phase 5 | P3 — Low      | Code Quality             | 3             | Low             |
|         |               |                          | **Total: 26** |                 |

---

## Phase 1: CasCor Training Failure (P0 — Critical)

> **Blocks**: All releases, deployments, and downstream development.
> **Prerequisite**: None
> **Repository**: juniper-cascor

### Step 1.1: Fix Walrus Operator Precedence Bug

- [ ] **Task 1.1.1**: Add parentheses to walrus operator expression at `cascade_correlation.py:1708`
- [ ] **Task 1.1.2**: Write unit test verifying `snapshot_path` receives actual path string, not boolean
- [ ] **Task 1.1.3**: Audit all other walrus operator usages in the file for same precedence issue

**Files**: `src/cascade_correlation/cascade_correlation.py`

### Step 1.2: Fix WebSocket Coroutine Leak

- [ ] **Task 1.2.1**: Change `except RuntimeError` to `except Exception` in `broadcast_from_thread()`
- [ ] **Task 1.2.2**: Add coroutine `close()` call in the exception handler
- [ ] **Task 1.2.3**: Write unit test simulating non-RuntimeError exception during broadcast

**Files**: `src/api/websocket/manager.py`

### Step 1.3: Fix Exception Propagation in Lifecycle Manager

- [ ] **Task 1.3.1**: Add state machine update to "failed" in `_run_training()` exception handler
- [ ] **Task 1.3.2**: Add WebSocket failure broadcast in exception handler
- [ ] **Task 1.3.3**: Write integration test verifying state transitions to "failed" on training exception
- [ ] **Task 1.3.4**: Write integration test verifying WebSocket receives "training_failed" event

**Files**: `src/api/lifecycle/manager.py`

### Step 1.4: Fix Drain Thread Queue Timing

- [ ] **Task 1.4.1**: Add initialization guard to drain thread's queue polling
- [ ] **Task 1.4.2**: Add graceful wait with configurable timeout for queue availability
- [ ] **Task 1.4.3**: Write unit test with delayed queue creation

**Files**: `src/api/lifecycle/manager.py`

### Step 1.5: Fix SharedMemory Lifecycle Management

- [ ] **Task 1.5.1**: Add try/finally cleanup guard for partially-created SharedMemory blocks
- [ ] **Task 1.5.2**: Ensure `_active_shm_blocks` list is consistent on exception
- [ ] **Task 1.5.3**: Write unit test for SharedMemory cleanup on creation failure

**Files**: `src/cascade_correlation/cascade_correlation.py`

### Step 1.6: Remove Dead Code

- [ ] **Task 1.6.1**: Remove `global shared_object_dict` at line 2923
- [ ] **Task 1.6.2**: Remove `import datetime as pd` at line 39
- [ ] **Task 1.6.3**: Remove duplicate `self.snapshot_counter = 0` at line 779
- [ ] **Task 1.6.4**: Verify no remaining references to removed code

**Files**: `src/cascade_correlation/cascade_correlation.py`

### Step 1.7: Extract Shared ActivationWithDerivative Class

- [ ] **Task 1.7.1**: Create `src/utils/activation.py` with canonical class definition
- [ ] **Task 1.7.2**: Update `cascade_correlation.py` to import from `src/utils/activation.py`
- [ ] **Task 1.7.3**: Update `candidate_unit.py` to import from `src/utils/activation.py`
- [ ] **Task 1.7.4**: Write unit test verifying both modules use the same class and ACTIVATION_MAP
- [ ] **Task 1.7.5**: Run full test suite to verify no import/pickle regressions

**Files**: `src/utils/activation.py` (new), `src/cascade_correlation/cascade_correlation.py`, `src/candidate_unit/candidate_unit.py`

### Phase 1 Verification

- [ ] Run full cascor test suite (2926 tests)
- [ ] Manual test: start training, verify first epoch completes without failure
- [ ] Manual test: verify WebSocket broadcasts metrics during training
- [ ] Manual test: verify training runs through multiple epochs

---

## Phase 2: Canopy-CasCor Connection (P0 — Critical)

> **Blocks**: All canopy monitoring functionality
> **Prerequisite**: Phase 1 (training must work for connection to matter)
> **Repositories**: juniper-cascor-client, juniper-canopy

### Step 2.1: Fix Client Response Key Mismatch

- [ ] **Task 2.1.1**: Change `"data"` to `"details"` in `client.py:76` `is_ready()` method
- [ ] **Task 2.1.2**: Update client test mocks to use `"details"` key
- [ ] **Task 2.1.3**: Run client test suite

**Files**: `juniper-cascor-client/juniper_cascor_client/client.py`, `juniper-cascor-client/tests/test_client.py`

### Step 2.2: Fix Connection Gate in Service Adapter

- [ ] **Task 2.2.1**: Change `is_ready()` to `is_alive()` in `cascor_service_adapter.py:122-128`
- [ ] **Task 2.2.2**: Update adapter tests
- [ ] **Task 2.2.3**: Run canopy test suite

**Files**: `juniper-canopy/src/backend/cascor_service_adapter.py`, `juniper-canopy/tests/test_cascor_service_adapter.py`

### Phase 2 Verification

- [ ] Integration test: canopy connects to running cascor instance
- [ ] Verify `/api/status` returns populated data
- [ ] Verify WebSocket connection established

---

## Phase 3: Canopy UI Fixes (P1 — High)

> **Prerequisite**: Phase 2 (connection must work for UI to receive data)
> **Repository**: juniper-canopy

### Step 3.1: Fix Tab Ordering

- [ ] **Task 3.1.1**: Verify tab order matches requirements; reorder if needed in `dashboard_manager.py:1075-1134`
- [ ] **Task 3.1.2**: Update TAB_SIDEBAR_CONFIG to match new ordering

**Files**: `src/frontend/dashboard_manager.py`

### Step 3.2: Fix Network Topology Output Nodes

- [ ] **Task 3.2.1**: Investigate `_build_network_graph()` for duplicate output node entries
- [ ] **Task 3.2.2**: Add node deduplication by ID before rendering
- [ ] **Task 3.2.3**: Write test verifying single output node for single-output network

**Files**: `src/frontend/components/network_visualizer.py`

### Step 3.3: Fix Convergence Threshold Display

- [ ] **Task 3.3.1**: Trace field mapping from cascor status endpoint to sidebar input
- [ ] **Task 3.3.2**: Fix any key misalignment causing wrong value display
- [ ] **Task 3.3.3**: Write test verifying correct field binding

**Files**: `src/frontend/dashboard_manager.py`

### Step 3.4: Fix Cassandra Panel API URL

- [ ] **Task 3.4.1**: Replace Flask request context with settings-based URL construction
- [ ] **Task 3.4.2**: Write test verifying URL construction without Flask context
- [ ] **Task 3.4.3**: Test Cassandra tab renders without error

**Files**: `src/frontend/components/cassandra_panel.py`

### Step 3.5: Fix Decision Boundary Display

- [ ] **Task 3.5.1**: Add Plotly `scaleanchor` for equal aspect ratio
- [ ] **Task 3.5.2**: Update container style for proper height/width ratio
- [ ] **Task 3.5.3**: Implement hidden node history store
- [ ] **Task 3.5.4**: Add replay controls (slider/play button)
- [ ] **Task 3.5.5**: Write test for history replay functionality

**Files**: `src/frontend/components/decision_boundary.py`

### Step 3.6: Fix Dataset View Display

- [ ] **Task 3.6.1**: Add proper aspect ratio to dataset scatter plot
- [ ] **Task 3.6.2**: Implement callback to query juniper-data for available generators
- [ ] **Task 3.6.3**: Pre-populate dropdown with current training dataset
- [ ] **Task 3.6.4**: Rename sidebar section from "Spiral Dataset" to "Current Dataset"
- [ ] **Task 3.6.5**: Implement dynamic field rendering based on selected dataset type
- [ ] **Task 3.6.6**: Implement Generate Dataset workflow (stop → generate → display → compatibility check)
- [ ] **Task 3.6.7**: Add user prompt for incompatible dataset/network combinations

**Files**: `src/frontend/components/dataset_plotter.py`, `src/frontend/dashboard_manager.py`

### Step 3.7: Fix Snapshots Refresh Button Position

- [ ] **Task 3.7.1**: Move refresh button and status from main header to "Available Snapshots" section
- [ ] **Task 3.7.2**: Update layout and styling

**Files**: `src/frontend/components/hdf5_snapshots_panel.py`

### Phase 3 Verification

- [ ] Visual verification of all tabs in correct order
- [ ] Visual verification of network topology with correct output node count
- [ ] Visual verification of decision boundary with correct aspect ratio
- [ ] Visual verification of dataset view with populated dropdown
- [ ] Visual verification of Cassandra tab without error
- [ ] Run full canopy test suite

---

## Phase 4: Dark Mode Styling (P2 — Medium)

> **Prerequisite**: None (independent of Phases 1-3)
> **Repository**: juniper-canopy

### Step 4.1: Fix Candidate Loss Graph Background

- [ ] **Task 4.1.1**: Set `paper_bgcolor` and `plot_bgcolor` to transparent in graph figures
- [ ] **Task 4.1.2**: Add dark mode font color toggling based on theme state
- [ ] **Task 4.1.3**: Visual verification in dark mode

**Files**: `src/frontend/components/candidate_metrics_panel.py`

### Step 4.2: Fix Parameters Tab Tables

- [ ] **Task 4.2.1**: Remove inline background styles that override dark mode CSS
- [ ] **Task 4.2.2**: Add dark mode class or ensure CSS variables apply correctly
- [ ] **Task 4.2.3**: Visual verification in dark mode

**Files**: `src/frontend/components/parameters_panel.py`, `src/frontend/assets/dark_mode.css`

### Step 4.3: Fix Tutorial Tab Tables

- [ ] **Task 4.3.1**: Same approach as 4.2 for tutorial tables
- [ ] **Task 4.3.2**: Visual verification in dark mode

**Files**: `src/frontend/components/tutorial_panel.py`, `src/frontend/assets/dark_mode.css`

### Phase 4 Verification

- [ ] All tabs render correctly in dark mode
- [ ] No white backgrounds on tables, graphs, or cards
- [ ] WCAG AA contrast compliance maintained

---

## Phase 5: Code Quality (P3 — Low)

> **Prerequisite**: Phase 1 completed
> **Repository**: juniper-cascor

### Step 5.1: Clean Up Dead Code and Redundancies

- [ ] **Task 5.1.1**: Remove misleading `import datetime as pd`
- [ ] **Task 5.1.2**: Remove duplicate `self.snapshot_counter = 0`
- [ ] **Task 5.1.3**: Add SharedMemory partial creation cleanup guard

### Step 5.2: Improve Exception Handling

- [ ] **Task 5.2.1**: Add specific exception types to `_stop_workers` handler
- [ ] **Task 5.2.2**: Add SharedMemory error context to exception messages

### Phase 5 Verification

- [ ] Full test suite passes
- [ ] No linting errors
- [ ] Pre-commit hooks pass

---

## Execution Timeline

```bash
Phase 1 (P0) ──────────────────────────► [CRITICAL - DO FIRST]
         │
Phase 2 (P0) ──────────────► [CRITICAL - AFTER PHASE 1]
         │
Phase 3 (P1) ─────────────────────────────────► [HIGH - AFTER PHASE 2]
         │
Phase 4 (P2) ────────► [MEDIUM - PARALLEL WITH ANY PHASE]
         │
Phase 5 (P3) ───► [LOW - AFTER PHASE 1]
```

**Dependency Chain**: Phase 1 → Phase 2 → Phase 3
**Independent**: Phase 4 (can run in parallel)
**After Phase 1**: Phase 5

---

## Completion Criteria

1. All 2926 cascor tests pass
2. All ~2900 canopy tests pass
3. Training runs to completion without failure
4. Canopy successfully monitors cascor training in real-time
5. All tabs render correctly in both light and dark mode
6. No error messages in Cassandra tab
7. Network topology shows correct output node count
8. Decision boundary displays with correct aspect ratio
9. Dataset dropdown populated with available generators
10. All changes committed, pushed, and PRs created
