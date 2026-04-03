# Juniper Project: Regression Remediation Development Roadmap

**Date**: 2026-04-02
**Reference**: `REGRESSION_ANALYSIS_2026-04-02.md`, `REGRESSION_REMEDIATION_PLAN_2026-04-02.md`
**Author**: Claude Code (Principal Engineer)

---

## Roadmap Summary

| Phase     | Description              | Tasks  | Priority      | Dependencies                 |
|-----------|--------------------------|--------|---------------|------------------------------|
| 1         | CasCor Training Fix      | 6      | P0 (Critical) | None                         |
| 2         | Canopy-CasCor Connection | 4      | P0 (Critical) | Phase 1                      |
| 3         | Canopy UI Fixes          | 14     | P1 (High)     | None (parallel with Phase 2) |
| 4         | Validation & Release     | 6      | P1 (High)     | Phases 1, 2, 3               |
| **Total** |                          | **30** |               |                              |

---

## Phase 1: CasCor Training Fix

**Repository**: juniper-cascor
**Branch**: `fix/training-regression-opt5`
**Priority**: P0 - BLOCKS ALL OTHER WORK

### Task 1.1: Remove _fallback_tensors from OPT-5 Metadata

- **Issue**: CRIT-1
- **File**: `src/cascade_correlation/cascade_correlation.py`
- **Line**: 1835
- **Action**: Delete `shm_metadata["_fallback_tensors"] = (candidate_input, y, residual_error)`
- **Status**: [ ] Pending

### Task 1.2: Update Sequential Fallback to Regenerate Legacy Tasks

- **Issue**: CRIT-1
- **File**: `src/cascade_correlation/cascade_correlation.py`
- **Lines**: 1974-1982 (`_execute_candidate_training`)
- **Action**: When parallel training fails, regenerate tasks using legacy tuple format before calling `_execute_sequential_training`. The method needs access to original tensors (`candidate_input`, `y`, `residual_error`) — pass them as parameters or capture from the enclosing `train_candidates` call.
- **Depends On**: Task 1.1
- **Status**: [ ] Pending

### Task 1.3: Update _build_candidate_inputs SharedMemory Error Handling

- **Issue**: CRIT-1
- **File**: `src/cascade_correlation/cascade_correlation.py`
- **Lines**: 2856-2861
- **Action**: When SharedMemory reconstruction fails and no `_fallback_tensors` exist, raise the exception immediately instead of looking for fallback. Remove the `_fallback_tensors` code path entirely.
- **Depends On**: Task 1.1
- **Status**: [ ] Pending

### Task 1.4: Adjust Weight Magnitude Validation Threshold

- **Issue**: CRIT-1 (contributing)
- **File**: `src/cascade_correlation/cascade_correlation.py`
- **Line**: 2155
- **Action**: Change `_RESULT_MAX_WEIGHT_MAGNITUDE = 100.0` to `_RESULT_MAX_WEIGHT_MAGNITUDE = 1000.0`. Add warning log (without rejection) for values 100.0-1000.0.
- **Status**: [ ] Pending

### Task 1.5: Fix Walrus Operator Precedence

- **Issue**: CRIT-2
- **File**: `src/cascade_correlation/cascade_correlation.py`
- **Line**: 1708
- **Action**: Change `if snapshot_path := self.create_snapshot() is not None:` to `if (snapshot_path := self.create_snapshot()) is not None:`. Add try/except wrapper.
- **Status**: [ ] Pending

### Task 1.6: Run CasCor Test Suite

- **Issue**: Validation
- **Action**: `cd src/tests && bash scripts/run_tests.bash -v`
- **Depends On**: Tasks 1.1-1.5
- **Status**: [ ] Pending

---

## Phase 2: Canopy-CasCor Connection Fix

**Repository**: juniper-cascor-client (primary), juniper-canopy (secondary)
**Branch**: `fix/canopy-cascor-connection`
**Priority**: P0
**Depends On**: Phase 1

### Task 2.1: Fix is_ready() Data Contract Mismatch

- **Issue**: HIGH-1
- **Repository**: juniper-cascor-client
- **File**: Client library readiness check
- **Action**: Handle both `"data"` and `"details"` response keys:

  ```python
  data = result.get("data") or result.get("details") or {}
  return data.get("network_loaded", False)
  ```

- **Status**: [ ] Pending

### Task 2.2: Fix connect() to Use is_alive()

- **Issue**: HIGH-1
- **Repository**: juniper-canopy
- **File**: `src/backend/service_backend.py`
- **Action**: Change `connect()` to gate on `is_alive()` instead of `is_ready()`
- **Depends On**: Task 2.1
- **Status**: [ ] Pending

### Task 2.3: Update FakeCascorClient for Test Compatibility

- **Issue**: HIGH-1
- **Repository**: juniper-cascor-client
- **File**: `testing/fake_client.py`
- **Action**: Ensure `health_ready()` returns response matching real server format
- **Depends On**: Task 2.1
- **Status**: [ ] Pending

### Task 2.4: Run Client and Canopy Test Suites

- **Issue**: Validation
- **Action**: Run tests in both repos
- **Depends On**: Tasks 2.1-2.3
- **Status**: [ ] Pending

---

## Phase 3: Canopy UI Fixes

**Repository**: juniper-canopy
**Branch**: `fix/canopy-ui-regressions`
**Priority**: P1
**Can run in parallel with Phase 2**

### Task 3.1: Candidate Metrics Graph Dark Mode

- **Issue**: HIGH-2
- **File**: `src/frontend/components/candidate_metrics_panel.py`
- **Lines**: 529-580 (`_create_candidate_loss_figure`)
- **Action**:
  1. Add `theme: str = "light"` parameter to `_create_candidate_loss_figure()`
  2. Conditionally apply `plotly_dark` template, `#242424` backgrounds for dark mode
  3. Update callback (lines 304-309) to pass current theme from `dcc.Store`
- **Status**: [ ] Pending

### Task 3.2: Decision Boundary Aspect Ratio

- **Issue**: HIGH-4
- **File**: `src/frontend/components/decision_boundary.py`
- **Line**: 149
- **Action**: Add `scaleanchor="x"` to yaxis layout and adjust container to preserve aspect ratio
- **Status**: [ ] Pending

### Task 3.3: Dataset View Aspect Ratio

- **Issue**: HIGH-6
- **File**: `src/frontend/components/dataset_plotter.py`
- **Line**: 222
- **Action**: Same approach as Task 3.2
- **Status**: [ ] Pending

### Task 3.4: Dataset Dropdown Population

- **Issue**: HIGH-7
- **File**: `src/frontend/components/dataset_plotter.py`, `dashboard_manager.py`
- **Action**:
  1. Add callback to fetch generator list from juniper-data service
  2. Populate dropdown with generator names
  3. Pre-select current dataset
  4. Add error handling for unavailable service
- **Status**: [ ] Pending

### Task 3.5: Dataset Sidebar Dynamic Labels

- **Issue**: HIGH-7
- **File**: `src/frontend/dashboard_manager.py`
- **Action**: Change "Spiral Dataset" section header to "Current Dataset" and dynamically update field visibility based on selected generator type
- **Status**: [ ] Pending

### Task 3.6: Generate Dataset Workflow

- **Issue**: HIGH-7
- **File**: `src/frontend/dashboard_manager.py`, `dataset_plotter.py`
- **Action**: Implement full generate dataset workflow:
  1. Stop training on button click
  2. Generate new dataset via juniper-data
  3. Update scatter plot
  4. Update feature distributions
  5. Check network compatibility
  6. Prompt user if incompatible
- **Status**: [ ] Pending

### Task 3.7: Decision Boundary Replay

- **Issue**: HIGH-5
- **File**: `src/frontend/components/decision_boundary.py`
- **Action**: New feature - add hidden node history store, slider, play/pause controls
- **Note**: Can be deferred to a follow-up sprint if Phase 3 scope is too large
- **Status**: [ ] Pending

### Task 3.8: HDF5 Snapshots Dark Mode Colors

- **Issue**: MED-1
- **File**: `src/frontend/components/hdf5_snapshots_panel.py`
- **Lines**: 111, 123, 216
- **Action**: Replace `#2c3e50` -> `var(--header-color)`, `#6c757d` -> `var(--text-muted)`, `#e9ecef` -> `var(--bg-secondary)`
- **Status**: [ ] Pending

### Task 3.9: Cassandra Panel Dark Mode Colors

- **Issue**: MED-2
- **File**: `src/frontend/components/cassandra_panel.py`
- **Line**: 200
- **Action**: Replace `#2c3e50` -> `var(--header-color)`
- **Status**: [ ] Pending

### Task 3.10: Cassandra Panel API Fix

- **Issue**: HIGH-3
- **File**: `src/frontend/components/cassandra_panel.py`
- **Action**: Replace HTTP self-call pattern with direct use of `cassandra_client.py` backend module in callbacks. Or add proxy routes to `main.py`.
- **Status**: [ ] Pending

### Task 3.11: HDF5 Snapshots Refresh Button Placement

- **Issue**: MED-3
- **File**: `src/frontend/components/hdf5_snapshots_panel.py`
- **Lines**: 113-124
- **Action**: Move refresh button and status message from title to "Available Snapshots" section
- **Status**: [ ] Pending

### Task 3.12: Verify Parameters Tab Dark Mode

- **Issue**: MED-4
- **Action**: Visual verification. If tables still show white backgrounds, apply CSS variable pattern from Step 3.8.
- **Status**: [ ] Pending

### Task 3.13: Verify Tutorial Tab Dark Mode

- **Issue**: MED-5
- **Action**: Visual verification. Same as Task 3.12.
- **Status**: [ ] Pending

### Task 3.14: Run Canopy Test Suite

- **Issue**: Validation
- **Action**: `cd src && pytest tests/ -v --tb=short`
- **Depends On**: Tasks 3.1-3.13
- **Status**: [ ] Pending

---

## Phase 4: Validation & Release

**Priority**: P1
**Depends On**: Phases 1, 2, 3

### Task 4.1: Full Integration Test

- **Action**: Start all services (juniper-data, juniper-cascor, juniper-canopy) and verify end-to-end training flow
- **Status**: [ ] Pending

### Task 4.2: Visual Regression Testing

- **Action**: Review all tabs in both light and dark modes. Verify all identified issues are resolved.
- **Status**: [ ] Pending

### Task 4.3: Commit All Changes

- **Action**: Stage, commit, and push changes to each affected repo's working branch
- **Status**: [ ] Pending

### Task 4.4: Create Pull Requests

- **Action**: Create PRs for each affected repository:
  1. juniper-cascor: `fix/training-regression-opt5`
  2. juniper-canopy: `fix/canopy-ui-regressions`
  3. juniper-cascor-client: `fix/canopy-cascor-connection` (if modified)
- **Status**: [ ] Pending

### Task 4.5: Merge Pull Requests

- **Action**: Merge in dependency order: cascor-client -> cascor -> canopy
- **Status**: [ ] Pending

### Task 4.6: Worktree Cleanup

- **Action**: Run `scripts/worktree_cleanup.bash` for each worktree
- **Depends On**: Task 4.5
- **Status**: [ ] Pending

---

## Execution Order Summary

```text
[CRITICAL PATH]
Task 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 (CasCor fix)
                                            ↓
                                    Task 2.1 → 2.2 → 2.3 → 2.4 (Connection fix)
                                            ↓
                                    Task 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6

[PARALLEL PATH]
Task 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 → 3.8 → 3.9 → 3.10 → 3.11 → 3.12 → 3.13 → 3.14
(Can start immediately, independent of Phase 1/2)
                                                                                            ↓
                                                                                    Task 4.1 (joins)
```

---

## Scope Control Notes

- **Task 3.7 (Decision Boundary Replay)**: This is a new feature, not a regression fix. It can be deferred to a follow-up sprint without blocking the release.
- **Task 3.6 (Generate Dataset Workflow)**: Complex multi-step workflow. Can be implemented incrementally — start with dataset switching, add compatibility checks in a follow-up.
- **HIGH-8 (Network Topology Output Nodes)**: Requires investigation of cascor network configuration. May be a valid configuration rather than a bug. Deferred pending investigation.

---

*Roadmap generated from analysis in REGRESSION_ANALYSIS_2026-04-02.md and plan in REGRESSION_REMEDIATION_PLAN_2026-04-02.md.*
