# Juniper Integration Development Plan

**Created**: 2026-02-05
**Last Updated**: 2026-02-05
**Version**: 1.0.0
**Status**: Active - Planning
**Author**: Development Team

---

## Executive Summary

This document consolidates **all outstanding integration work** across the three Juniper applications: **JuniperCascor** (Cascade Correlation Neural Network backend), **JuniperCanopy** (Web-based monitoring frontend), and **JuniperData** (Dataset generation service). It combines:

1. Outstanding items extracted from four existing planning documents
2. Newly identified issues from rigorous source code review

All items are prioritized into phases based on severity, blocking potential, integration risk, and effort.

### Source Documents Evaluated

| Document | Location | Status |
| --- | --- | --- |
| JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN.md | JuniperCascor/notes/ | Phases 0-4 Complete, Phase 5 Deferred |
| INTEGRATION_ROADMAP.md | JuniperCascor/notes/ (symlinked to JuniperData/notes/) | Most issues RESOLVED |
| PRE-DEPLOYMENT_ROADMAP.md | JuniperCascor/notes/ (symlinked to JuniperData/notes/) | P0-P1 RESOLVED, some P2-P3 remaining |
| PRE-DEPLOYMENT_ROADMAP-2.md | JuniperCascor/notes/ (symlinked to JuniperData/notes/) | 74% complete, 26% remaining |

### Outstanding Work Summary

| Category | Critical | High | Medium | Low | Total |
| --- | --- | --- | --- | --- | --- |
| Code Issues (from source review) | 3 | 3 | 8 | 3 | 17 |
| Documentation Items (from roadmaps) | 0 | 1 | 5 | 30+ | 36+ |
| **Total** | **3** | **4** | **13** | **33+** | **53+** |

---

## Table of Contents

1. [Phase 1: Critical Integration Blockers](#phase-1-critical-integration-blockers)
2. [Phase 2: High-Priority Integration Gaps](#phase-2-high-priority-integration-gaps)
3. [Phase 3: Medium-Priority Quality and Completeness](#phase-3-medium-priority-quality-and-completeness)
4. [Phase 4: Deferred and Future Enhancements](#phase-4-deferred-and-future-enhancements)
5. [Appendix A: Canopy Enhancement Backlog (CAN-001 through CAN-021)](#appendix-a-canopy-enhancement-backlog)
6. [Appendix B: Cascor Enhancement Backlog (CAS-001 through CAS-010)](#appendix-b-cascor-enhancement-backlog)
7. [Appendix C: Source Document Cross-Reference](#appendix-c-source-document-cross-reference)

---

## Phase 1: Critical Integration Blockers

These items represent code paths that will **crash or fail silently** when the real CasCor backend is connected. They must be resolved before any non-demo integration testing.

### INT-CRIT-001: Real Backend Control Not Implemented

**Source**: Code review
**Application**: Juniper Canopy
**Location**: `src/main.py:433-442`
**Severity**: CRITICAL
**Effort**: M (2-4 days)
**Blocks**: All real-backend WebSocket control

**Problem**: The `/ws/control` WebSocket endpoint rejects ALL commands when `cascor_integration` is active. The handler returns a hardcoded error response:

```python
elif cascor_integration:
    # TODO: Implement real backend control
    await websocket_manager.send_personal_message(
        {"ok": False, "error": "Real backend control not yet implemented"},
        websocket,
    )
```

**Impact**: Start, stop, pause, resume, and reset commands are non-functional against the real CasCor backend. Users cannot control training from the Canopy UI when connected to a live backend.

**Required Actions**:

- [ ] Implement command routing to `CascorIntegration` methods for start, stop, pause, resume, reset
- [ ] Map demo mode command semantics to real backend equivalents (e.g., `start` → `start_training_background()`, `stop` → `request_training_stop()`)
- [ ] Add state broadcasting after each command execution
- [ ] Add integration tests for real backend control path (mocked CascorIntegration)

**Dependencies**: INT-CRIT-003 (get_network_data missing)

---

### INT-CRIT-002: Decision Boundary Incomplete for Real Backend

**Source**: Code review
**Application**: Juniper Canopy
**Location**: `src/main.py:779-788`
**Severity**: CRITICAL
**Effort**: M (2-4 days)
**Blocks**: Decision boundary visualization with real backend

**Problem**: The `/api/decision_boundary` endpoint retrieves the prediction function from `cascor_integration.get_prediction_function()` via walrus operator, logs a message, but **never computes the decision boundary**. It falls through to the 503 error response regardless.

```python
if cascor_integration:
    if predict_fn := cascor_integration.get_prediction_function():
        # TODO: Add Similar logic for real cascor network
        system_logger.info(f"... Predict Function: {predict_fn}")
        # pass

return JSONResponse({"error": "No decision boundary data available"}, status_code=503)
```

**Impact**: The Dataset/Decision Boundary tab always shows "No data available" when connected to a real CasCor backend.

**Required Actions**:

- [ ] Implement grid computation using `predict_fn` (mirror demo mode logic at lines ~730-777)
- [ ] Extract grid generation into a shared helper to avoid code duplication
- [ ] Handle edge cases (no dataset loaded, network not trained)
- [ ] Add integration test with mocked prediction function

---

### INT-CRIT-003: `get_network_data()` Method Missing from CascorIntegration

**Source**: Code review
**Application**: Juniper Canopy
**Location**: `src/main.py:627` (caller), `src/backend/cascor_integration.py` (missing method)
**Severity**: CRITICAL
**Effort**: M (2-4 days)
**Blocks**: Network statistics endpoint with real backend

**Problem**: The `/api/statistics` endpoint calls `cascor_integration.get_network_data()`, but this method does not exist on the `CascorIntegration` class. This will raise `AttributeError` at runtime.

**Impact**: Network statistics tab fails when connected to real CasCor backend.

**Required Actions**:

- [ ] Implement `get_network_data()` on `CascorIntegration` that returns a dict with keys: `input_weights`, `hidden_weights`, `output_weights`, `hidden_biases`, `output_biases`, `threshold_function`, `optimizer`
- [ ] Extract data from the underlying CasCor network object (`self.network`)
- [ ] Add thread-safe access (use existing `self.metrics_lock` or dedicated lock)
- [ ] Add unit test for the new method

---

## Phase 2: High-Priority Integration Gaps

These items represent significant functional gaps or architectural risks that should be addressed before beta deployment.

### INT-HIGH-001: `save_snapshot()` / `load_snapshot()` Missing from CascorIntegration

**Source**: Code review
**Application**: Juniper Canopy
**Location**: `src/main.py:1137,1330` (callers), `src/backend/cascor_integration.py` (missing methods)
**Severity**: HIGH
**Effort**: M (2-4 days)
**Original Ref**: Code review finding

**Problem**: The HDF5 snapshot API endpoints check `hasattr(cascor_integration, "save_snapshot")` and `hasattr(cascor_integration, "load_snapshot")`. Neither method exists, so the code falls through to a minimal HDF5 fallback that only stores basic metadata—not the actual network state.

**Impact**: Snapshot save/load in real backend mode produces incomplete snapshots without network weights, hidden units, or training history.

**Required Actions**:

- [ ] Implement `save_snapshot(path, description=None)` delegating to CasCor's `CascadeHDF5Serializer`
- [ ] Implement `load_snapshot(path)` to restore network state
- [ ] Wire into the existing snapshot API endpoints
- [ ] Add integration tests for round-trip snapshot save/load

---

### INT-HIGH-002: Async/Sync Boundary Documentation and Testing

**Source**: Code review + PRE-DEPLOYMENT_ROADMAP-2 (P1-NEW-003)
**Application**: Juniper Canopy
**Severity**: HIGH
**Effort**: M (2-3 days)

**Problem**: The async/sync boundary between FastAPI (async) and CasCor training (sync/threaded) is implemented via `ThreadPoolExecutor` and `run_in_executor`, but:

- No integration tests verify WebSocket responsiveness during active training
- The `schedule_broadcast()` function uses `run_coroutine_threadsafe` but has no tests
- Training callbacks (`on_metrics_update`, `on_topology_change`, `on_cascade_add`) are registered but untested in integration context

**Required Actions**:

- [ ] Test WebSocket responsiveness during training (manual verification at minimum)
- [ ] Add integration test that starts training and verifies WebSocket messages arrive
- [ ] Document threading model in code comments or architecture doc

**Original Ref**: PRE-DEPLOYMENT_ROADMAP-2 P1-NEW-003 action item: "Test WebSocket responsiveness during training"

---

### INT-HIGH-003: Tests Never Exercise Real Backend Path

**Source**: Code review
**Application**: Juniper Canopy
**Severity**: HIGH
**Effort**: L (1-2 weeks)

**Problem**: `conftest.py` forces `CASCOR_DEMO_MODE=1` for all tests. No test exercises the `cascor_integration` code paths in `main.py`. The 3 CRITICAL issues above (INT-CRIT-001/002/003) would have been caught by integration tests with a mocked `CascorIntegration`.

**Required Actions**:

- [ ] Create test fixture that provides a mocked `CascorIntegration` instance
- [ ] Add integration tests for real-backend code paths in main.py (control, topology, metrics, statistics, decision boundary, snapshots)
- [ ] Mark tests with `@pytest.mark.integration` and `@pytest.mark.requires_cascor` as appropriate
- [ ] Keep demo mode tests as-is for fast CI; add backend-path tests as separate suite

---

### INT-HIGH-004: JuniperData Client Not Actively Used

**Source**: Code review + JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN Phase 4
**Application**: Juniper Canopy
**Severity**: HIGH (integration completeness)
**Effort**: S-M (1-3 days)

**Problem**: `src/juniper_data_client/client.py` exists (Phase 4 deliverable) with `create_dataset()`, `download_artifact_npz()`, and `get_preview()` methods, and is integrated into `demo_mode.py` and `cascor_integration.py`. However:

- No `JUNIPER_DATA_URL` configuration exists in `conf/app_config.yaml`
- No `docker-compose` entry for JuniperData service
- No E2E integration tests verify the full flow with a live JuniperData service
- Demo mode generates synthetic data internally, bypassing JuniperData entirely when `JUNIPER_DATA_URL` is not set

**Required Actions**:

- [ ] Add `JUNIPER_DATA_URL` to `conf/app_config.yaml` with appropriate default
- [ ] Add JuniperData service entry to `conf/docker-compose.yaml`
- [ ] Add E2E integration test with live JuniperData service (marked `@pytest.mark.e2e`)
- [ ] Document dataset source switching in user-facing docs

**Original Ref**: JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN Section 14 Remaining Work Item 3

---

## Phase 3: Medium-Priority Quality and Completeness

### INT-MED-001: Cascor Code Coverage Below 90% Target

**Source**: PRE-DEPLOYMENT_ROADMAP (CASCOR-P2-001), PRE-DEPLOYMENT_ROADMAP-2 (P2-NEW-001)
**Application**: Juniper Cascor
**Severity**: MEDIUM
**Effort**: L-XL (ongoing)
**Status**: IN PROGRESS (~67% overall, target 90%)

**Current Coverage by Module**:

| Module | Current | Target |
| --- | --- | --- |
| `cascade_correlation.py` | ~61% | 85% |
| `candidate_unit.py` | ~81% | 90% |
| `snapshot_serializer.py` | ~80% | 90% |
| `profiling/` | ~90% | 80% (met) |
| `log_config/` | ~60% | 80% |

**Required Actions**:

- [ ] Continue adding unit tests for uncovered paths in `cascade_correlation.py`
- [ ] Reach 90% target for `candidate_unit.py` (currently near goal at 81%)
- [ ] Reach 90% target for `snapshot_serializer.py` (currently near goal at 80%)
- [ ] Improve `log_config/` coverage from 60% to 80%

---

### INT-MED-002: CI/CD Coverage Gates Not Enforced (Cascor)

**Source**: PRE-DEPLOYMENT_ROADMAP-2 (P2-NEW-002)
**Application**: Juniper Cascor
**Severity**: MEDIUM
**Effort**: S (1-2 hours)
**Status**: NOT STARTED

**Problem**: No coverage threshold enforcement in the Cascor CI/CD pipeline. Current CI generates reports but does not fail on regressions.

**Required Actions**:

- [ ] Add `coverage report --fail-under=80` to CI
- [ ] Configure coverage thresholds per module
- [ ] Add coverage badge to README

---

### INT-MED-003: Type Errors - Gradual Fix

**Source**: PRE-DEPLOYMENT_ROADMAP-2 (P2-NEW-006)
**Application**: Juniper Cascor
**Severity**: MEDIUM
**Effort**: L (ongoing)
**Status**: IN PROGRESS

**Problem**: Type checking enabled with `continue-on-error` in CI. Many type errors exist across the codebase.

**Required Actions**:

- [ ] Run mypy and categorize errors by severity
- [ ] Fix critical type errors in core modules (`cascade_correlation.py`, `candidate_unit.py`)
- [ ] Gradually increase type strictness
- [ ] Remove `continue-on-error` once stable

---

### INT-MED-004: Candidate Factory Refactor

**Source**: PRE-DEPLOYMENT_ROADMAP (P3-001)
**Application**: Juniper Cascor
**Severity**: MEDIUM
**Effort**: M (2-4 days)
**Status**: PARTIAL (analysis complete)

**Problem**: `CandidateUnit` instances are created in 3 different locations with inconsistent parameter patterns. Only `_create_candidate_unit()` is the designated factory.

**Recommendation**: The multiprocessing worker cannot easily use the factory due to serialization constraints. Document as intentional design decision rather than refactoring.

**Required Actions**:

- [ ] Document the 3 creation sites and rationale for each
- [ ] Add code comments explaining why multiprocessing worker creates directly
- [ ] Consider if `fit()` method creation can use factory pattern

---

### INT-MED-005: Remote Workers Untested

**Source**: Code review + PRE-DEPLOYMENT_ROADMAP-2 (P1-NEW-002 future actions)
**Application**: Juniper Canopy
**Severity**: MEDIUM
**Effort**: L (1-2 weeks)

**Problem**: The RemoteWorkerClient REST API endpoints (`/api/remote/*`) are implemented but:

- No integration tests exist for remote worker functionality
- No cross-platform testing has been performed
- Worker deployment procedure is undocumented

**Required Actions**:

- [ ] Add integration tests for remote worker REST endpoints (mocked backend)
- [ ] Test distributed training across at least 2 platforms (deferred until needed)
- [ ] Document worker deployment procedure

**Original Ref**: PRE-DEPLOYMENT_ROADMAP-2 P1-NEW-002 future enhancement items

---

### INT-MED-006: Cassandra/Redis Integration Gaps

**Source**: Code review
**Application**: Juniper Canopy
**Severity**: MEDIUM
**Effort**: M (2-4 days)

**Problem**: Backend services (Cassandra for persistence, Redis for caching) have implementation stubs but limited error handling:

- Cassandra cache invalidation strategy is not documented
- Redis error handling has gaps (connection failures may surface as unhandled exceptions)
- No health checks for backend services beyond basic connectivity

**Required Actions**:

- [ ] Review and document Cassandra cache invalidation strategy
- [ ] Add defensive error handling for Redis connection failures
- [ ] Add health check endpoints for Cassandra and Redis connectivity
- [ ] Add integration tests with service mocks

---

### INT-MED-007: Monitoring Loop Race Conditions

**Source**: Code review (related to PRE-DEPLOYMENT_ROADMAP CANOPY-P1-003, now FIXED)
**Application**: Juniper Canopy
**Location**: `src/backend/cascor_integration.py`
**Severity**: MEDIUM
**Effort**: S-M (1-2 days)

**Problem**: While CANOPY-P1-003 (metrics extraction race condition) was fixed by adding `self.metrics_lock`, the monitoring loop may still have edge cases:

- The lock covers metrics extraction but not topology extraction timing
- Training thread may broadcast stale data if lock contention is high
- No metrics for lock contention or monitoring loop latency

**Required Actions**:

- [ ] Audit all shared state access in monitoring loop
- [ ] Add timing metrics for monitoring loop iterations
- [ ] Test under simulated high-frequency updates

---

### INT-MED-008: Legacy Spiral Generator Code Cleanup

**Source**: JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN Section 14 Remaining Work Item 1
**Application**: Juniper Cascor
**Severity**: MEDIUM
**Effort**: M (2-4 days)

**Problem**: Legacy spiral data generation code remains in `spiral_problem.py` as fallback. Once JuniperData service availability is guaranteed, this can be removed.

**Trigger**: Remove when JuniperData service is deployed with high availability.

**Required Actions**:

- [ ] Document legacy code boundary clearly in source
- [ ] Create removal plan (files, imports, tests to update)
- [ ] Execute removal when JuniperData HA is confirmed

---

## Phase 4: Deferred and Future Enhancements

### INT-DEF-001: True IPC Architecture (Cascor-Canopy Process Separation)

**Source**: PRE-DEPLOYMENT_ROADMAP-2 (P1-NEW-001)
**Severity**: HIGH (deferred by design)
**Effort**: XL (2-4 weeks)
**Status**: DEFERRED

**Problem**: Current architecture embeds CasCor within the Canopy process. No true inter-process communication exists.

**Impact**:

- Cannot run CasCor training independently
- Cannot scale training on a different machine
- Cannot have multiple Canopy frontends observe a single training session
- Training failures crash the entire Canopy application

**Deferral Rationale**: P1-NEW-002 (RemoteWorkerClient) and P1-NEW-003 (async training) provide sufficient capability without architectural upheaval.

**Revisit Triggers**:

- Hard cancellation of training is required
- Training regularly crashes the UI process
- Multiple concurrent training jobs are needed
- Remote training clusters are deployed

---

### INT-DEF-002: GPU Support

**Source**: PRE-DEPLOYMENT_ROADMAP (P3-003), PRE-DEPLOYMENT_ROADMAP-2 (P3-NEW-003)
**Application**: Juniper Cascor
**Severity**: LOW (enhancement)
**Effort**: XL (2-4 weeks)
**Status**: NOT STARTED

**Required Actions**:

- [ ] Assess GPU memory requirements
- [ ] Add device configuration to `CascadeCorrelationConfig`
- [ ] Refactor tensor operations for GPU compatibility
- [ ] Add GPU tests (marked with `@pytest.mark.gpu`)
- [ ] Benchmark GPU vs CPU performance

---

### INT-DEF-003: Continuous Profiling (Grafana Pyroscope)

**Source**: PRE-DEPLOYMENT_ROADMAP-2 (P3-NEW-004)
**Application**: Juniper Cascor
**Severity**: LOW (infrastructure)
**Effort**: L (1-2 weeks)
**Status**: NOT STARTED

**Required Actions**:

- [ ] Deploy Grafana Pyroscope (Docker)
- [ ] Integrate pyroscope-io SDK into Cascor
- [ ] Create Grafana dashboards
- [ ] Set up performance regression alerting
- [ ] Integrate torch.profiler for GPU operations

---

### INT-DEF-004: Client Package Consolidation

**Source**: JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN Section 14 Remaining Work Item 2
**Application**: All
**Severity**: LOW (code organization)
**Effort**: M (2-4 days)

**Problem**: Both JuniperCascor and JuniperCanopy have their own copy of `juniper_data_client/`. These should be consolidated into a shared package.

**Required Actions**:

- [ ] Evaluate packaging strategy (PyPI, git submodule, shared repo)
- [ ] Create shared `juniper_data_client` package
- [ ] Update both applications to use shared package
- [ ] Add version pinning to prevent drift

---

### INT-DEF-005: JuniperBranch Worker Package Extraction

**Source**: PRE-DEPLOYMENT_ROADMAP-2 (P1-NEW-002 deferred), CAS-004
**Application**: Juniper Cascor → new JuniperBranch application
**Severity**: LOW (future architecture)
**Effort**: L-XL (2-4 weeks)

**Problem**: Remote worker code should be extracted into a separate `JuniperBranch` application for OS-agnostic distributed training.

**Target Platforms**: Ubuntu, Raspberry Pi OS, Debian, Fedora/RockyLinux/AlmaLinux

---

### INT-DEF-006: Extended Data Sources (Phase 5)

**Source**: JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN Phase 5
**Application**: JuniperData
**Severity**: LOW (future feature)
**Effort**: L-XL (staged)
**Status**: DEFERRED

**Problem**: Phase 5 of the spiral data extraction plan covers additional data sources beyond the spiral generator: S3/GCS providers, HuggingFace datasets, database-backed datasets.

**Trigger**: Implement when new dataset types are needed.

---

## Appendix A: Canopy Enhancement Backlog

These are pre-beta Canopy enhancements from PRE-DEPLOYMENT_ROADMAP-2 Section 7.1. All are **NOT STARTED**.

| ID | Module | Name | Description | Effort Est. |
| --- | --- | --- | --- | --- |
| CAN-001 | Training Metrics | Training Loss Time Window | Moving window dropdown for Training Loss graph | S |
| CAN-002 | Training Metrics | Custom Rolling Time Window | Custom time window input for Training Loss graph | S |
| CAN-003 | Training Metrics | Candidate Pool Availability | Retain and display candidate pool data per node addition | M |
| CAN-004 | Meta Param Tuning | Meta Param Tuning Tab | New tab for all exposed meta parameter tuning | L |
| CAN-005 | Meta Param Tuning | Pin/Unpin Meta Params | Pin selected params from Tuning tab to side menu | M |
| CAN-006 | Meta Param Tuning | Network Train Epoch Param | Tunable: epochs before next candidate addition | S |
| CAN-007 | Meta Param Tuning | Candidate Pool Train Epoch | Tunable: candidate pool training epochs | S |
| CAN-008 | Meta Param Tuning | Candidate Pool Node Count | Tunable: number of prospective nodes in pool | S |
| CAN-009 | Meta Param Tuning | Correlation Threshold | Tunable: correlation threshold for candidates | S |
| CAN-010 | Meta Param Tuning | Optimizer Type | Tunable: network optimizer selection | S |
| CAN-011 | Meta Param Tuning | Activation Function | Tunable: activation function selection | S |
| CAN-012 | Meta Param Tuning | Candidate Node Select Num | Tunable: number of top candidates selected | S |
| CAN-013 | Meta Param Tuning | Candidate Node Integration | Tunable: connection pattern for added nodes | M |
| CAN-014 | Training Metrics | Snapshot Captures Tuning | Snapshots capture meta param values throughout session | M-L |
| CAN-015 | Training Metrics | Snapshot Replay with Tuning | Replay snapshots with tunable params, fork into new session | L |
| CAN-016a | All | Layout Save/Load | Save/load complete dashboard state and customizations | M |
| CAN-016b | Dataset | Import/Generate Dataset | New Dataset button: local file, remote URL, or JuniperData | M |
| CAN-017 | All | Tooltips | Hover tooltips for all dashboard controls | M |
| CAN-018 | All | Tutorial Text | Right-click detailed tutorial descriptions with doc links | M-L |
| CAN-019 | All | Tutorial Walkthrough | Step-by-step highlighted tutorial mode | L |
| CAN-020 | All | Hierarchy Level Selection | Network selection at hierarchy level > 0 | M-L |
| CAN-021 | All | Population Selection | Network selection within population at a hierarchy | M |

**Recommended Priority Order** (for pre-beta):

1. **CAN-004** (Meta Param Tuning tab) - Foundation for CAN-005 through CAN-013
2. **CAN-006 through CAN-012** (Individual tunable params) - Build on CAN-004
3. **CAN-001, CAN-002** (Time window controls) - Quick UI wins
4. **CAN-016b** (Dataset import) - JuniperData integration surface
5. **CAN-003** (Candidate pool history) - Training insight
6. **CAN-014, CAN-015** (Snapshot tuning/replay) - Advanced training features
7. **CAN-016a, CAN-017, CAN-018, CAN-019** (UX polish) - Pre-release polish
8. **CAN-005, CAN-013** (Pin/unpin, node integration) - Power user features
9. **CAN-020, CAN-021** (Hierarchy/population) - Depends on CAS-008/CAS-009

---

## Appendix B: Cascor Enhancement Backlog

These are pre-beta Cascor enhancements from PRE-DEPLOYMENT_ROADMAP-2 Section 7.2. All are **NOT STARTED** unless noted.

| ID | Module | Name | Description | Effort Est. | Notes |
| --- | --- | --- | --- | --- | --- |
| CAS-001 | Data Generation | Extract Spiral Generator | Extract spiral generator into JuniperData | L | Phases 0-4 COMPLETE (JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN) |
| CAS-002 | Epoch Definition | Separate Epoch Limits | Separate epoch limits for full network vs candidate nodes | M | NOT STARTED |
| CAS-003 | Training Iterations | Max Train Session Iterations | Limit total iterations per training session | S-M | NOT STARTED |
| CAS-004 | Remote Workers | Extract Remote Worker Code | Extract into JuniperBranch application | L-XL | Deferred (see INT-DEF-005) |
| CAS-005 | Common Modules | Extract Common Dependencies | Shared modules for Cascor and Branch | M-L | Deferred (depends on CAS-004) |
| CAS-006 | Auto-Snapshot | Accuracy Ratchet | Auto-snapshot on new best accuracy | M | NOT STARTED |
| CAS-007 | Testing | Optimize Slow Tests | Reduce 45-min test suite to <= 5 min | L | NOT STARTED |
| CAS-008 | Network Hierarchy | Hierarchy Management | Multi-hierarchical CasCor network training | XL | NOT STARTED |
| CAS-009 | Network Population | Population Management | Population initialization at hierarchy level | XL | NOT STARTED |
| CAS-010 | Snapshot Storage | Vector DB Storage | Store snapshots in vector DB indexed by UUID | M-L | NOT STARTED |

**Recommended Priority Order** (for pre-beta):

1. **CAS-002** (Separate epoch limits) - Foundational training parameter
2. **CAS-003** (Max iterations) - Training control
3. **CAS-006** (Accuracy ratchet) - Data preservation
4. **CAS-007** (Optimize slow tests) - Developer productivity
5. **CAS-008, CAS-009** (Hierarchy/population) - Core architecture extension
6. **CAS-010** (Vector DB) - Advanced persistence

---

## Appendix C: Source Document Cross-Reference

This table maps each outstanding item back to its source document for traceability.

| Item ID | Source Document | Original ID | Status in Source |
| --- | --- | --- | --- |
| INT-CRIT-001 | Code review | N/A (TODO in main.py:435) | Newly identified |
| INT-CRIT-002 | Code review | N/A (TODO in main.py:783) | Newly identified |
| INT-CRIT-003 | Code review | N/A (main.py:627) | Newly identified |
| INT-HIGH-001 | Code review | N/A (main.py:1137,1330) | Newly identified |
| INT-HIGH-002 | PRE-DEPLOYMENT_ROADMAP-2 | P1-NEW-003 action item | Partially complete |
| INT-HIGH-003 | Code review | N/A | Newly identified |
| INT-HIGH-004 | SPIRAL_DATA_GEN_REFACTOR_PLAN | Section 14, Item 3 | Not started |
| INT-MED-001 | PRE-DEPLOYMENT_ROADMAP, ROADMAP-2 | CASCOR-P2-001, P2-NEW-001 | In progress |
| INT-MED-002 | PRE-DEPLOYMENT_ROADMAP-2 | P2-NEW-002 | Not started |
| INT-MED-003 | PRE-DEPLOYMENT_ROADMAP-2 | P2-NEW-006 | In progress |
| INT-MED-004 | PRE-DEPLOYMENT_ROADMAP | P3-001 | Partial |
| INT-MED-005 | PRE-DEPLOYMENT_ROADMAP-2 | P1-NEW-002 future items | Deferred |
| INT-MED-006 | Code review | N/A | Newly identified |
| INT-MED-007 | Code review (related to CANOPY-P1-003) | N/A | Newly identified |
| INT-MED-008 | SPIRAL_DATA_GEN_REFACTOR_PLAN | Section 14, Item 1 | Not started |
| INT-DEF-001 | PRE-DEPLOYMENT_ROADMAP-2 | P1-NEW-001 | Deferred |
| INT-DEF-002 | PRE-DEPLOYMENT_ROADMAP, ROADMAP-2 | P3-003, P3-NEW-003 | Not started |
| INT-DEF-003 | PRE-DEPLOYMENT_ROADMAP-2 | P3-NEW-004 | Not started |
| INT-DEF-004 | SPIRAL_DATA_GEN_REFACTOR_PLAN | Section 14, Item 2 | Not started |
| INT-DEF-005 | PRE-DEPLOYMENT_ROADMAP-2, CAS-004 | P1-NEW-002 deferred | Deferred |
| INT-DEF-006 | SPIRAL_DATA_GEN_REFACTOR_PLAN | Phase 5 | Deferred |
| CAN-001..021 | PRE-DEPLOYMENT_ROADMAP-2 | Section 7.1 | Not started |
| CAS-001..010 | PRE-DEPLOYMENT_ROADMAP-2 | Section 7.2 | Mixed (CAS-001 complete) |

---

## Implementation Schedule

### Recommended Execution Order

| Phase | Duration | Items | Prerequisite |
| --- | --- | --- | --- |
| Phase 1 | 1-2 weeks | INT-CRIT-001, INT-CRIT-002, INT-CRIT-003 | None |
| Phase 2 | 2-3 weeks | INT-HIGH-001 through INT-HIGH-004 | Phase 1 |
| Phase 3 | 3-4 weeks | INT-MED-001 through INT-MED-008 | Phase 1 |
| Phase 4 | Ongoing | INT-DEF-*, CAN-*, CAS-* | Phase 2 |

### Phase 1 Critical Path

```
INT-CRIT-003 (get_network_data)
    ↓
INT-CRIT-001 (backend control)  ←→  INT-CRIT-002 (decision boundary)
    ↓
INT-HIGH-003 (backend path tests) — validates all Phase 1 fixes
```

---

## Document History

| Date | Version | Author | Changes |
| --- | --- | --- | --- |
| 2026-02-05 | 1.0.0 | Development Team | Initial creation from 4 source documents + code review |
