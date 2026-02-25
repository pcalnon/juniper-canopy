# JuniperCanopy Post-Release Development Roadmap

**Project**: JuniperCanopy - Web-based Monitoring Frontend
**Created**: 2026-02-17
**Last Updated**: 2026-02-25
**Author**: Paul Calnon
**Status**: Active - Comprehensive Post-Release Assessment
**Source**: Full codebase audit of all notes/ files with validation against source code (2026-02-17)

---

## Table of Contents

- [Overview](#overview)
- [Audit Methodology](#audit-methodology)
- [Phase 0 — Critical: Integration Gaps](#phase-0--critical-integration-gaps)
- [Phase 1 — High: Backend Integration and Testing](#phase-1--high-backend-integration-and-testing)
- [Phase 2 — Medium: Code Quality and CI/CD](#phase-2--medium-code-quality-and-cicd)
- [Phase 3 — Enhancement: Dashboard Features](#phase-3--enhancement-dashboard-features)
- [Phase 4 — Future: Deferred and Architectural](#phase-4--future-deferred-and-architectural)
- [Validated as Complete](#validated-as-complete)
- [Cross-Project Items](#cross-project-items)
- [Summary](#summary)
- [Design Analysis](#design-analysis)
- [Document History](#document-history)

---

## Overview

This document is the consolidated, validated, and prioritized roadmap for all JuniperCanopy work items identified during a comprehensive audit of all notes/ files (2026-02-17). Every item has been validated against the actual codebase to confirm its current status.

### Source Documents Evaluated

| Document                                           | Location             | Items Extracted                                        |
| -------------------------------------------------- | -------------------- | ------------------------------------------------------ |
| PRE-DEPLOYMENT_ROADMAP.md                          | notes/               | P0-P2 items, profiling roadmap                         |
| INTEGRATION_ROADMAP.md                             | notes/               | Integration status items                               |
| INTEGRATION_ROADMAP-01.md                          | notes/               | INT-CRIT, INT-HIGH, INT-MED, INT-DEF, CAN/CAS backlogs |
| INTEGRATION_DEVELOPMENT_PLAN.md                    | notes/               | 53+ organized integration items                        |
| CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md            | notes/               | CAN-INT items (Phases 0-3)                             |
| TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md    | notes/               | Epics 4.1-4.4, SK items                                |
| TEST_SUITE_AUDIT_CANOPY_AMP.md                     | notes/               | AMP audit findings                                     |
| TEST_SUITE_AUDIT_CANOPY_CLAUDE.md                  | notes/               | Claude audit findings                                  |
| CANOPY_CASCOR_INTEGRATION_REGRESSION_2026-02-11.md | notes/               | 6 regression fix designs                               |
| REGRESSION_ANALYSIS_STARTUP_FAILURE_2026-02-09.md  | notes/               | 5 startup failure fixes                                |
| VALIDATION_REPORT_2026-01-12.md                    | notes/               | Validation recommendations                             |
| FIX_FAILING_TESTS.md                               | notes/               | Test fix items                                         |
| DEVELOPMENT_ROADMAP.md                             | notes/development/   | Phase status tracking                                  |
| IMPLEMENTATION_PLAN.md                             | notes/development/   | Implementation status                                  |
| phase0-3 READMEs                                   | notes/development/   | Phase-level status                                     |
| DEMO_HANG_ANALYSIS_2026-01-03.md                   | notes/analysis/      | Bash script fix items                                  |
| fixes/*.md (6 files)                               | notes/fixes/         | Bash/testing fix items                                 |
| releases/*.md (8 files)                            | notes/releases/      | Coverage gaps, known issues                            |
| pull_requests/*.md (9 files)                       | notes/pull_requests/ | Deployment preparation items                           |

---

## Audit Methodology

1. **Compilation**: Read all 45+ notes files across notes/, notes/development/, notes/analysis/, notes/fixes/, notes/releases/, notes/pull_requests/, notes/research/, and notes/templates/.
2. **Extraction**: Identified every item in a non-completed state (Not Started, In Progress, Incomplete, Stalled, Deferred, Partial).
3. **De-duplication**: Cross-referenced items appearing in multiple documents to eliminate duplicates.
4. **Validation**: Checked each item against the actual source code using symbolic search and pattern matching.
5. **Prioritization**: Organized validated items into development phases by criticality and dependency.
6. **Design Analysis**: Provided high-level design options for significant items.

---

## Phase 0 — Critical: Integration Gaps

Items that affect core functionality when running with a real CasCor backend.

### CAN-CRIT-001: Decision Boundary for Real Backend

**Status**: NOT IMPLEMENTED
**Priority**: CRITICAL
**Source**: INTEGRATION_ROADMAP-01.md (INT-CRIT-002), INTEGRATION_DEVELOPMENT_PLAN.md
**Module**: `src/main.py`
**Validation**: Confirmed — `main.py:822` contains a TODO comment. The `/api/decision_boundary` endpoint only returns demo data; no real backend path exists.

**Description**: The decision boundary visualization endpoint has no implementation for real CasCor backend data. When `CASCOR_DEMO_MODE` is not set, the endpoint returns empty or incorrect data. This is a core visualization feature that is non-functional in production mode.

**Design Options**:

- **Option A (Recommended)**: Add `get_decision_boundary_data()` method to `CascorServiceAdapter` that queries the real CasCor backend for grid predictions, then format the response identically to the demo mode output. Minimal frontend changes required.
- **Option B**: Implement a generic prediction endpoint that accepts arbitrary input grids, then have the frontend compute the decision boundary visualization client-side. More flexible but requires frontend changes.
- **Option C**: Add a WebSocket channel for streaming decision boundary updates during training. Better real-time UX but higher implementation complexity.

**Estimated Scope**: Medium (1-2 files, ~100-200 lines)
**Dependencies**: Requires understanding of CasCor's prediction API
**Files**: `src/main.py`, `src/backend/cascor_service_adapter.py`

---

### CAN-CRIT-002: Save/Load Snapshot Missing from CascorServiceAdapter

**Status**: NOT IMPLEMENTED
**Priority**: CRITICAL
**Source**: INTEGRATION_ROADMAP-01.md (INT-HIGH-001), INTEGRATION_DEVELOPMENT_PLAN.md
**Module**: `src/backend/cascor_service_adapter.py`
**Validation**: Confirmed — `save_snapshot()` and `load_snapshot()` methods do not exist in `CascorServiceAdapter`. HDF5 snapshot creation exists in `main.py` but only for demo mode state.

**Description**: The `CascorServiceAdapter` class has no methods for persisting and restoring training state via the real CasCor backend. This prevents training session recovery, checkpoint-based resumption, and the snapshot features planned in CAN-014/CAN-015.

**Design Options**:

- **Option A (Recommended)**: Add `save_snapshot(path)` and `load_snapshot(path)` methods to `CascorServiceAdapter` that delegate to CasCor's native serialization (PyTorch `state_dict` or custom format). Store metadata (epoch, metrics, timestamp) in a sidecar JSON.
- **Option B**: Use HDF5 format matching the existing demo mode snapshot format. Provides format consistency but may not capture all CasCor internal state.
- **Option C**: Implement a snapshot service that manages versioned snapshots with metadata indexing. More robust but higher complexity.

**Estimated Scope**: Medium (1-2 files, ~150-250 lines)
**Dependencies**: CasCor serialization API
**Files**: `src/backend/cascor_service_adapter.py`, potentially `src/main.py` snapshot endpoints

---

## Phase 1 — High: Backend Integration and Testing

Items that affect testing coverage, backend integration reliability, or production readiness.

### CAN-HIGH-001: Startup Health Check with HTTP Probe

**Status**: NOT IMPLEMENTED
**Priority**: HIGH
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-012)
**Module**: `src/main.py`
**Validation**: Confirmed — `main.py` lifespan validates `JUNIPER_DATA_URL` configuration presence but makes no HTTP request to verify the JuniperData service is actually reachable.

**Description**: During application startup, JuniperCanopy validates that `JUNIPER_DATA_URL` is configured but does not perform a health check HTTP request. If JuniperData is unreachable, the failure occurs only when a user first attempts a data operation, with no clear error message.

**Design Options**:

- **Option A (Recommended)**: Add an HTTP GET to `{JUNIPER_DATA_URL}/health` during lifespan startup. Log warning and set a `juniper_data_available` flag if unreachable. Non-blocking — application still starts but degrades gracefully.
- **Option B**: Make JuniperData availability a hard requirement — fail startup if unreachable. Simpler but less flexible for development scenarios.

**Estimated Scope**: Small (1 file, ~30-50 lines)
**Files**: `src/main.py` (lifespan function)

---

### CAN-HIGH-002: NPZ Validation — Dtype and Shape Checks

**Status**: PARTIALLY IMPLEMENTED
**Priority**: HIGH
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-007)
**Module**: `src/backend/cascor_service_adapter.py`
**Validation**: Confirmed partial — key existence checks are implemented but dtype and shape validation are not.

**Description**: When loading NPZ dataset files, the code verifies that required keys exist but does not validate array dtypes or expected shapes. Malformed data could cause cryptic errors downstream during training.

**Estimated Scope**: Small (1 file, ~20-40 lines)
**Files**: `src/backend/cascor_service_adapter.py`

---

### CAN-HIGH-003: Async/Sync Boundary Testing

**Status**: NOT IMPLEMENTED
**Priority**: HIGH
**Source**: INTEGRATION_ROADMAP-01.md (INT-HIGH-002), INTEGRATION_DEVELOPMENT_PLAN.md
**Module**: `src/tests/`

**Description**: The ThreadPoolExecutor-based async/sync bridge (`start_training_background()`) has no dedicated tests. Edge cases like concurrent start requests, executor shutdown during training, and exception propagation across the boundary are untested.

**Estimated Scope**: Medium (1-2 new test files, ~200-300 lines)
**Files**: `src/tests/integration/test_async_boundary.py` (new)

---

### CAN-HIGH-004: Real Backend Path Test Coverage

**Status**: NOT IMPLEMENTED
**Priority**: HIGH
**Source**: INTEGRATION_ROADMAP-01.md (INT-HIGH-003), INTEGRATION_DEVELOPMENT_PLAN.md
**Module**: `src/tests/`

**Description**: No tests exercise the real backend code paths in `main.py` or `CascorServiceAdapter`. All tests run with `CASCOR_DEMO_MODE=1`. While this is correct for CI, there should be integration tests (gated behind `CASCOR_BACKEND_AVAILABLE`) that verify real backend behavior.

**Estimated Scope**: Large (2-3 new test files, ~400-600 lines)
**Files**: `src/tests/integration/test_real_backend.py` (new)

---

### CAN-HIGH-005: Remote Worker Integration

**Status**: NOT IMPLEMENTED
**Priority**: HIGH
**Source**: INTEGRATION_ROADMAP-01.md (INT-HIGH-004), INTEGRATION_DEVELOPMENT_PLAN.md
**Module**: `src/backend/cascor_service_adapter.py`

**Description**: `RemoteWorkerClient` integration is referenced in architecture docs but has no test coverage or verified integration path. Distributed training via remote workers is a planned capability.

**Estimated Scope**: Large (2-3 files, ~300-500 lines)
**Dependencies**: RemoteWorkerClient implementation in JuniperCascor
**Files**: `src/backend/cascor_service_adapter.py`, new test files

---

### CAN-HIGH-006: JuniperData Error Handling Standardization

**Status**: NOT STARTED
**Priority**: HIGH
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-011)
**Module**: `src/backend/`, `src/main.py`

**Description**: Standardize error handling for all JuniperData REST API interactions. Map HTTP status codes to user-friendly error messages. Implement consistent retry and timeout patterns.

**Estimated Scope**: Medium (2-3 files, ~100-200 lines)
**Files**: `src/backend/cascor_service_adapter.py`, `src/main.py`

---

### CAN-HIGH-007: Convert Skipped WebSocket Tests

**Status**: NOT STARTED
**Priority**: HIGH
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (SK-005, SK-006, SK-007)
**Module**: `src/tests/`

**Description**: Three WebSocket test groups are currently skipped with `requires_server` marker. These should be converted to work with the `TestClient` WebSocket interface for CI compatibility.

| ID     | Test                             | Current Reason  |
| ------ | -------------------------------- | --------------- |
| SK-005 | test_websocket_control.py        | requires_server |
| SK-006 | test_main_ws.py (subset)         | requires_server |
| SK-007 | test_websocket_state.py (subset) | requires_server |

**Estimated Scope**: Medium (3 files, ~150-250 lines modified)
**Files**: Various test files in `src/tests/integration/`

---

### CAN-HIGH-008: Main.py Coverage Gap (84% vs 95% Target)

**Status**: NOT IMPLEMENTED
**Priority**: HIGH
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-001), releases/RELEASE_NOTES_v0.25.0-alpha.md
**Module**: `src/main.py`, `src/tests/`

**Description**: `main.py` is at 84% test coverage against a 95% target for critical paths. The gap is primarily in real-backend code paths and error handling branches that are not exercised in demo mode.

**Estimated Scope**: Medium (1-2 test files, ~200-300 lines)
**Files**: `src/tests/unit/test_main_coverage*.py`, `src/tests/integration/test_main_coverage.py`

---

## Phase 2 — Medium: Code Quality and CI/CD

Items that improve code quality, CI/CD reliability, or developer experience.

### CAN-MED-001: Re-enable Remaining MyPy Disabled Codes

**Status**: PARTIALLY ADDRESSED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (PC-004)
**Module**: `.pre-commit-config.yaml`
**Validation**: Confirmed — 4 codes re-enabled (`call-arg`, `override`, `no-redef`, `index`). Seven remain disabled: `attr-defined`, `return-value`, `arg-type`, `assignment`, `var-annotated`, `misc`, `dict-item`.

**Description**: Re-enable the remaining MyPy error codes (`attr-defined`, `return-value`, `arg-type`, `assignment`, `var-annotated`, `misc`, `dict-item`) by fixing the underlying type annotation issues in the codebase. Each code requires identifying and fixing the specific violations.

**Estimated Scope**: Medium (5-10 files, ~50-100 line changes)
**Files**: `.pre-commit-config.yaml`, various source files with type violations

---

### CAN-MED-002: Re-enable E722 Bare Except in Flake8

**Status**: NOT ADDRESSED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (Epic 4.3)
**Module**: `.pre-commit-config.yaml`
**Validation**: Confirmed — E722 is still in the flake8 ignore list.

**Description**: E722 (`bare except`) is suppressed in the flake8 configuration. All bare `except:` clauses should be converted to specific exception types, then E722 should be removed from the ignore list.

**Estimated Scope**: Small-Medium (find and fix all bare except clauses)
**Files**: `.pre-commit-config.yaml`, source files with bare excepts

---

### CAN-MED-003: Include notes/ in Markdown Linting

**Status**: PARTIALLY ADDRESSED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (PC-006)
**Module**: `.pre-commit-config.yaml`
**Validation**: Confirmed — markdown linting includes `docs/` but excludes `notes/`.

**Description**: The markdownlint pre-commit hook only covers `docs/` directory. The `notes/` directory should be included to maintain consistent markdown quality across all documentation.

**Estimated Scope**: Small (1 file, ~5 lines)
**Files**: `.pre-commit-config.yaml`

---

### CAN-MED-004: Flake8 Configuration Standardization

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (CFG-01, CFG-02)
**Module**: Configuration files

**Description**: Consolidate flake8 configuration. Remove redundant pyproject.toml flake8 settings in favor of a single `.flake8` configuration file. Ensure consistency with pre-commit hook settings.

**Estimated Scope**: Small (2-3 config files)
**Files**: `.flake8` (new or existing), `pyproject.toml`, `.pre-commit-config.yaml`

---

### CAN-MED-005: contextlib.suppress Review

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (EXC-04)
**Module**: Various source files

**Description**: Review all bare `try/except: pass` patterns across the codebase and convert appropriate ones to `contextlib.suppress(SpecificException)` for clarity. This is related to CAN-MED-002 (E722) — fixing bare excepts may resolve both items.

**Estimated Scope**: Small-Medium (multiple files, ~30-50 line changes)
**Files**: Various source files

---

### CAN-MED-006: Training Monitoring Race Conditions

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-006)
**Module**: `src/main.py`, `src/communication/`

**Description**: Potential race conditions in training status monitoring when multiple WebSocket clients connect/disconnect during active training. Lock ordering and event propagation should be audited.

**Estimated Scope**: Medium (2-3 files, ~50-100 lines)
**Files**: `src/main.py`, `src/communication/websocket_manager.py`

---

### CAN-MED-007: Type Annotation Gaps

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-002)
**Module**: Various source files

**Description**: Several modules have incomplete type annotations. Adding proper type hints enables MyPy to catch more bugs and improves developer experience. Related to CAN-MED-001 (re-enabling MyPy codes).

**Estimated Scope**: Medium (5-10 files, ~100-200 line changes)
**Files**: Various source files

---

### CAN-MED-008: JuniperData Circuit Breaker Pattern

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-014)
**Module**: `src/backend/`

**Description**: Implement circuit breaker pattern for JuniperData REST API calls. After N consecutive failures, stop attempting calls for a cooldown period. Prevents cascade failures when JuniperData is unavailable.

**Estimated Scope**: Medium (1-2 files, ~100-150 lines)
**Files**: `src/backend/cascor_service_adapter.py` or new `src/backend/circuit_breaker.py`

---

### CAN-MED-009: JuniperData Metrics/Logging Integration

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-013)
**Module**: `src/backend/`, `src/logger/`

**Description**: Add structured logging and metrics for JuniperData API interactions (request count, latency, error rate). Enables monitoring and debugging of the integration.

**Estimated Scope**: Small-Medium (2-3 files, ~50-100 lines)
**Files**: `src/backend/cascor_service_adapter.py`, `src/logger/logger.py`

---

### CAN-MED-010: End-to-End Integration Tests

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-018)
**Module**: `src/tests/`

**Description**: Create end-to-end tests that exercise the full JuniperData integration path: dataset import, training with imported data, and results retrieval. Gated behind environment variable flags.

**Estimated Scope**: Large (1-2 new test files, ~300-400 lines)
**Files**: `src/tests/integration/test_juniper_data_e2e.py` (new)

---

### CAN-MED-011: Legacy Code Cleanup

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-007)
**Module**: Various

**Description**: Clean up legacy code patterns including stale `.pyc` files from deleted `constants.py` module, outdated CLAUDE.md references to `constants.py`, and deprecated code paths.

**Validation Note**: `src/constants.py` has been deleted from the codebase but stale `.pyc` files remain and CLAUDE.md still references `Constants` classes extensively.

**Estimated Scope**: Small-Medium (documentation and file cleanup)
**Files**: `CLAUDE.md`, stale `__pycache__` files

---

### CAN-MED-012: Error Handling Standardization

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-008)
**Module**: Various source files

**Description**: Standardize error handling patterns across the codebase. Define consistent error response formats for API endpoints. Ensure all user-facing errors provide actionable information.

**Estimated Scope**: Medium (5-10 files, ~100-200 lines)
**Files**: `src/main.py`, `src/backend/cascor_service_adapter.py`, various

---

### CAN-MED-013: Documentation Status Inconsistencies

**Status**: NOT ADDRESSED
**Priority**: MEDIUM
**Source**: notes/development/phase3/README.md, notes/development/IMPLEMENTATION_PLAN.md
**Validation**: Confirmed — P3-2 and P3-3 say "Not Started" inline but top-level says COMPLETE. IMPLEMENTATION_PLAN.md status is still "Active" with Phase 3 TBD.

**Description**: Several development documentation files have inconsistent status markers. These should be corrected to reflect actual implementation state.

**Estimated Scope**: Small (2-3 files, text corrections)
**Files**: `notes/development/phase3/README.md`, `notes/development/IMPLEMENTATION_PLAN.md`

---

### CAN-MED-014: Test Docstrings

**Status**: NOT STARTED
**Priority**: MEDIUM
**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md (CQ-002)
**Module**: `src/tests/`

**Description**: Add descriptive docstrings to test methods that lack them. Improves test readability and makes pytest output more informative.

**Estimated Scope**: Medium (many files, ~200-400 line additions)
**Files**: Various test files

---

## Phase 3 — Enhancement: Dashboard Features

New dashboard features and UX enhancements. These are the CAN-000 through CAN-021 items from the original pre-deployment roadmap. All are NOT STARTED.

### Dashboard: Meta Parameter Menu

#### CAN-000: Meta Parameter Updates Pause

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Menu
**Description**: Periodic updates to the Learning Rate, Hidden Units, max Epochs meta param fields should pause when the Apply Parameters button becomes active.
**Estimated Scope**: Small (1-2 files, ~30-50 lines)

---

### Dashboard: Training Metrics

#### CAN-001: Training Loss Time Window

**Status**: NOT STARTED
**Module**: Dashboard: Training Metrics
**Description**: Add a control (e.g., dropdown) to toggle/select the time window to display for the Training Loss over Time graph. "Moving Window".

**Design Options**:

- **Option A (Recommended)**: Dropdown with preset windows (Last 50, 100, 500, All). Simple, fast to implement.
- **Option B**: Slider control for continuous window adjustment. More flexible but more complex UX.

**Estimated Scope**: Medium (2-3 files, ~100-150 lines)

---

#### CAN-002: Custom Rolling Time Window

**Status**: NOT STARTED
**Module**: Dashboard: Training Metrics
**Description**: Add the ability to define a custom time window to display Training Loss over Time graph.
**Dependencies**: CAN-001 (builds on time window infrastructure)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-003: Candidate Pool Availability

**Status**: NOT STARTED
**Module**: Dashboard: Training Metrics
**Description**: Retain candidate pool data for each node(s) addition operation. Access that data by expanding "Previous Pools" entry (e.g., "Pool @ Epoch 471 - Best: cand_X (correlation)").
**Estimated Scope**: Large (3-4 files, ~200-300 lines)

---

#### CAN-014: Snapshot Captures with Tuning

**Status**: NOT STARTED
**Module**: Dashboard: Training Metrics
**Description**: Snapshotting complete (or in progress) network training session captures values of meta params, as they are tuned, throughout the training session, allowing the session to be replayed.
**Dependencies**: CAN-CRIT-002 (save/load snapshot infrastructure)
**Estimated Scope**: Large (3-5 files, ~300-500 lines)

---

#### CAN-015: Snapshot Replay with Tuning

**Status**: NOT STARTED
**Module**: Dashboard: Training Metrics
**Description**: When replaying a training snapshot, allow tuning of any/all meta params so that training session stops being a replay and becomes a new training session that can, itself, be snapshotted.
**Dependencies**: CAN-014 (snapshot capture), CAN-CRIT-002 (save/load)
**Estimated Scope**: Large (3-5 files, ~300-500 lines)

---

### Dashboard: Meta Parameter Tuning

#### CAN-004: Meta Parameter Tuning Tab

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add a new Tab to Canopy dashboard: Meta Parameter Tuning, in addition to left side menu, that allows all exposed meta params to be set/tuned in Canopy dashboard.

**Design Options**:

- **Option A (Recommended)**: New Dash tab component with a grid of parameter controls (sliders, dropdowns, numeric inputs). Each control sends updates via WebSocket `/ws/control`. Reuses existing parameter validation from `ConfigManager`.
- **Option B**: Embed parameter controls in a collapsible side panel instead of a separate tab. Always visible but takes less screen real estate from other tabs.

**Estimated Scope**: Large (4-6 files, ~400-600 lines)

---

#### CAN-005: Pin/Unpin Meta Parameters

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add feature to "Pin" and "Unpin" selected tunable meta params, from Meta Param Tuning Tab, to left side Meta Param menu.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Medium (2-3 files, ~100-200 lines)

---

#### CAN-006: Network Train Epoch Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for number of full network epochs before the next candidate node addition to be set/tuned in Canopy dashboard during a training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-007: Candidate Pool Train Epoch Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for number of candidate node pool training epochs to be set/tuned in Canopy dashboard during a training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-008: Candidate Pool Node Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for number of prospective nodes in the candidate pool to be set/tuned in Canopy dashboard during a training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-009: Correlation Threshold Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for correlation threshold of candidate pool nodes to be set/tuned in Canopy dashboard during a training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-010: Optimizer Type Meta Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for Network Optimizer to be set/tuned in Canopy dashboard during a training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-011: Activation Function Parameter

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for Network Activation Function to be set/tuned in Canopy dashboard during training session.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-012: Candidate Node Selection Count

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for number of top candidate nodes in pool, with correlation values > threshold, that are selected for addition to the full network.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small (1-2 files, ~50-80 lines)

---

#### CAN-013: Candidate Node Integration Mode

**Status**: NOT STARTED
**Module**: Dashboard: Meta Param Tuning
**Description**: Add tunable meta parameter for selected nodes' network integration: Input Only, Input & All Hidden, Input & Prev Hidden, All Hidden, and Prev Hidden that is tunable during training.
**Dependencies**: CAN-004 (tuning tab)
**Estimated Scope**: Small-Medium (1-2 files, ~80-120 lines)

---

### Dashboard: General

#### CAN-016a: Implement Layout Save/Load

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: Enhance the "Save Layout" feature in Training Metrics tab to save current state of dashboard including all app customizations.

**Design Options**:

- **Option A (Recommended)**: Serialize dashboard state to JSON in browser localStorage. Include tab selection, parameter values, graph zoom levels, pinned parameters.
- **Option B**: Server-side storage via REST API endpoint. Enables sharing layouts across devices/sessions but requires persistence layer.

**Estimated Scope**: Medium-Large (3-5 files, ~200-400 lines)

---

#### CAN-016b: Import/Generate New Dataset

**Status**: NOT STARTED
**Module**: Dashboard: Dataset
**Description**: Add "New Dataset" button to Dataset Tab allowing loading local dataset file, downloading remote dataset URL, or importing dataset attached resource — JuniperData via REST API.
**Dependencies**: JuniperData integration (CAN-HIGH-001, CAN-HIGH-006)
**Estimated Scope**: Large (3-5 files, ~300-500 lines)

---

#### CAN-017: Add Tool Tips

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: Hovering the mouse over any Canopy Dashboard Control should provide a concise "tool-tip" description. Tool tip should include "Right click for more info" statement.
**Estimated Scope**: Medium (many files, ~100-200 lines spread across components)

---

#### CAN-018: Add Tutorial Text for Controls

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: Right-clicking any Canopy Dashboard Control should provide moderately detailed tutorial-style description. Description includes link to related App Documentation File section.
**Dependencies**: CAN-017 (tooltip infrastructure)
**Estimated Scope**: Large (many files, ~300-500 lines)

---

#### CAN-019: Add Tutorial Walkthrough

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: Add walk-through style tutorial, with highlighted (and explained) next step in procedure, for Page, Tab, selected menu, or selected control.
**Dependencies**: CAN-017, CAN-018

**Design Options**:

- **Option A (Recommended)**: Use a tour library (e.g., `dash-bootstrap-components` popovers or a JavaScript tour library like Shepherd.js). Step-by-step overlays with highlighting.
- **Option B**: Custom implementation with overlay components and a step state machine. Full control but more development effort.

**Estimated Scope**: Large (5-8 files, ~500-800 lines)

---

#### CAN-020: Show Network at Hierarchy Level

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: For Hierarchy Level > 0, allow specific network selection via editable dropdown or moving slider with thumbnail preview row — error msg for invalid selection.
**Dependencies**: Multi-hierarchy CasCor support
**Estimated Scope**: Large (3-5 files, ~200-400 lines)

---

#### CAN-021: Show Network in Population

**Status**: NOT STARTED
**Module**: Dashboard: All
**Description**: For Network population > 1 at a given hierarchy, allow specific network selection via dropdown or by moving slider with thumbnail preview row.
**Dependencies**: CAN-020 (hierarchy support), population-based CasCor training
**Estimated Scope**: Large (3-5 files, ~200-400 lines)

---

## Phase 4 — Future: Deferred and Architectural

Items that are deferred due to scope, dependencies, or architectural decisions.

### CAN-DEF-001: True IPC Architecture

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: INTEGRATION_ROADMAP-01.md (P1-NEW-001), INTEGRATION_DEVELOPMENT_PLAN.md
**Deferral Rationale**: Async training (ThreadPoolExecutor) and RemoteWorkerClient provide sufficient capability without architectural upheaval.

**Description**: Current architecture embeds Cascor within the Canopy process. No actual inter-process communication between separately running instances. Prevents scaling, failure isolation, and multiple frontends.

**Design Options** (for future consideration):

- **Option A**: gRPC service boundary between Canopy and CasCor. Provides strong typing, streaming, and language independence.
- **Option B**: REST + WebSocket microservice architecture. CasCor runs as an independent service. Simpler but less efficient for streaming data.
- **Option C**: Message queue (Redis Streams / RabbitMQ) based decoupling. Best for eventual consistency and multi-consumer scenarios.

---

### CAN-DEF-002: Cassandra Integration Testing

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-004)

**Description**: Cassandra persistence layer has no integration tests. Testing requires a Cassandra instance (or embedded alternative).

---

### CAN-DEF-003: Redis Integration Testing

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-005)

**Description**: Redis caching/pub-sub layer has no integration tests. Testing requires a Redis instance.

---

### CAN-DEF-004: Remote Worker Test Coverage

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: INTEGRATION_ROADMAP-01.md (INT-MED-003)

**Description**: RemoteWorkerClient has no test coverage. Depends on CAN-HIGH-005 (remote worker integration) being implemented first.

---

### CAN-DEF-005: JuniperData Dataset Versioning

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-015)

**Description**: Support dataset versioning through JuniperData API. Track which dataset version was used for each training session.

---

### CAN-DEF-006: JuniperData Batch Operations

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-016)

**Description**: Support batch dataset operations (bulk import, bulk export, batch metadata updates) through JuniperData API.

---

### CAN-DEF-007: JuniperData Performance Benchmarks

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md (CAN-INT-019)

**Description**: Create performance benchmarks for JuniperData integration (dataset load times, API latency, throughput under load).

---

### CAN-DEF-008: Advanced Node Interactions (3D View)

**Status**: DEFERRED
**Priority**: LOW (deferred)
**Source**: notes/development/DEVELOPMENT_ROADMAP.md (P1-4 Phase 2)

**Description**: Advanced node interaction features for 3D network visualization, including rotation, zoom, node selection, and weight inspection.

---

## Validated as Complete

The following items were found in notes files as non-completed but were confirmed as implemented during codebase validation. They are documented here for audit trail purposes.

### INT-CRIT-001: Real Backend Control (COMPLETE)

**Source**: INTEGRATION_ROADMAP-01.md
**Validation**: `main.py:420-463` has full command routing for real backend (start, stop, pause, resume, reset). Implemented.

---

### INT-CRIT-003: get_network_data() Missing (COMPLETE)

**Source**: INTEGRATION_ROADMAP-01.md
**Validation**: `cascor_service_adapter.py:234` implements `get_network_data()`. Implemented.

---

### P0-11: Dark Mode Info Bar (COMPLETE)

**Source**: notes/development/phase0/README.md
**Validation**: `network_visualizer.py:417-430` implements dark mode info bar. Implemented.

---

### CAN-INT-010: Docker Compose JuniperData Service (COMPLETE)

**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md
**Validation**: `conf/docker-compose.yaml` defines `juniper-data` service with proper configuration. Implemented.

---

### Demo Hang Circular Dependency (COMPLETE)

**Source**: notes/analysis/DEMO_HANG_ANALYSIS_2026-01-03.md
**Validation**: `util/__get_project_dir.bash` no longer sources `common.conf`. Fixed.

---

### .coveragerc fail_under=80 (COMPLETE)

**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md
**Validation**: `.coveragerc:26` has `fail_under = 80`. Fixed.

---

### -p no:warnings Removed (COMPLETE)

**Source**: TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md
**Validation**: `pyproject.toml` no longer contains `-p no:warnings`. Fixed.

---

### INTEG-004: Blocking Training in FastAPI Async Context (COMPLETE)

**Source**: INTEGRATION_ROADMAP-01.md
**Validation**: ThreadPoolExecutor with max_workers=1 implemented. `start_training_background()` method exists in `CascorServiceAdapter`. Implemented.

---

### CAN-REF-001/002/003: JuniperData Integration Cross-References (COMPLETE)

**Source**: Original roadmap file
**Validation**: Client re-exports, YAML config, and Docker Compose all confirmed. Complete.

---

### CAN-INT-001/002/003: JuniperData Phase 0 Critical Items (COMPLETE)

**Source**: CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md
**Validation**: All Phase 0 critical JuniperData integration items confirmed complete.

---

## Cross-Project Items

Items identified during this audit that belong to JuniperCascor or JuniperData. These have been written to their respective `notes/` directories.

### JuniperCascor Items

See: `JuniperCascor/juniper_cascor/notes/JUNIPER-CASCOR_POST-RELEASE_DEVELOPMENT-ROADMAP.md`

- CAS-002 through CAS-010: CasCor enhancement backlog (9 items)
- Profiling roadmap tasks (16 items from PRE-DEPLOYMENT_ROADMAP.md)
- Backend-specific items (serialization API for snapshots, prediction grid API)

### JuniperData Items

See: `JuniperData/juniper_data/notes/JUNIPER-DATA_POST-RELEASE_DEVELOPMENT-ROADMAP.md`

- Dataset versioning API support
- Batch operations API
- Health check endpoint verification
- Performance benchmark requirements

---

## Summary

| Phase     | Category                      | Total  | Not Started | Partial | Complete | Deferred |
| --------- | ----------------------------- | ------ | ----------- | ------- | -------- | -------- |
| 0         | Critical Integration Gaps     | 2      | 2           | 0       | 0        | 0        |
| 0         | Critical (validated complete) | —      | —           | —       | 10       | —        |
| 1         | High: Backend/Testing         | 8      | 7           | 1       | 0        | 0        |
| 2         | Medium: Code Quality/CI       | 14     | 12          | 2       | 0        | 0        |
| 3         | Enhancement: Dashboard        | 23     | 23          | 0       | 0        | 0        |
| 4         | Future: Deferred              | 8      | 0           | 0       | 0        | 8        |
| **Total** |                               | **55** | **44**      | **3**   | **0**    | **8**    |

### Priority Distribution

| Priority    | Count | Description                                |
| ----------- | ----- | ------------------------------------------ |
| CRITICAL    | 2     | Core functionality gaps in production mode |
| HIGH        | 8     | Testing, integration, production readiness |
| MEDIUM      | 14    | Code quality, CI/CD, developer experience  |
| ENHANCEMENT | 23    | New dashboard features and UX improvements |
| DEFERRED    | 8     | Future architectural and integration items |

### Dependency Graph (Key Chains)

```bash
CAN-CRIT-002 (save/load snapshot)
  └─> CAN-014 (snapshot captures)
       └─> CAN-015 (snapshot replay with tuning)

CAN-004 (meta param tuning tab)
  └─> CAN-005 (pin/unpin)
  └─> CAN-006 through CAN-013 (individual parameters)

CAN-001 (time window)
  └─> CAN-002 (custom time window)

CAN-017 (tooltips)
  └─> CAN-018 (tutorial text)
       └─> CAN-019 (tutorial walkthrough)

CAN-020 (hierarchy selection)
  └─> CAN-021 (population selection)

CAN-HIGH-005 (remote worker integration)
  └─> CAN-DEF-004 (remote worker testing)
```

---

## Design Analysis

### Architecture Considerations

**Current State**: JuniperCanopy is a monolithic FastAPI + Dash application with embedded CasCor backend integration via `CascorServiceAdapter` class. Training runs in a `ThreadPoolExecutor` thread. WebSocket communication provides real-time updates. Demo mode simulates the full backend for development.

**Key Design Decisions for Phase 0-1**:

1. **Decision Boundary Implementation (CAN-CRIT-001)**: The recommended approach (Option A) adds a method to `CascorServiceAdapter` that queries the real CasCor backend for predictions over a grid. This maintains the existing pattern where backend-specific logic lives in `CascorServiceAdapter` and the API endpoints remain backend-agnostic. The frontend requires zero changes.

2. **Snapshot Persistence (CAN-CRIT-002)**: The recommended approach (Option A) uses CasCor's native serialization format (PyTorch `state_dict`) with a JSON metadata sidecar. This captures complete training state including optimizer state and learning rate schedules. HDF5 (Option B) provides format consistency with demo mode but may lose CasCor-specific state.

3. **JuniperData Health Check (CAN-HIGH-001)**: The graceful degradation approach (Option A) is recommended over hard failure (Option B) because JuniperData is not required for core training functionality. The health check flag enables conditional UI elements.

**Key Design Decisions for Phase 3 (Dashboard)**:

1. **Meta Parameter Tuning Tab (CAN-004)**: This is the foundation for CAN-005 through CAN-013. The tab should be designed with a pluggable parameter control system so individual parameters (CAN-006 through CAN-013) can be added incrementally. Each parameter control should be a reusable Dash component.

2. **Tutorial System (CAN-017 through CAN-019)**: The three-tier approach (tooltips → right-click detail → walkthrough) should share a common content database. Tool tip text, tutorial text, and walkthrough steps should be defined in a single configuration file per component, avoiding content duplication.

3. **Layout Persistence (CAN-016a)**: Browser localStorage (Option A) is recommended for the initial implementation. Server-side storage can be added later as an enhancement without changing the serialization format.

### Risk Assessment

| Risk                                     | Likelihood | Impact | Mitigation                                               |
| ---------------------------------------- | ---------- | ------ | -------------------------------------------------------- |
| CasCor serialization API changes         | Medium     | High   | Abstract behind interface in CascorServiceAdapter           |
| WebSocket race conditions during scaling | Medium     | Medium | Audit lock ordering (CAN-MED-006) before adding features |
| Dashboard feature scope creep            | High       | Medium | Strict dependency chains — implement in order            |
| Test coverage regression                 | Low        | High   | Maintain coverage gates in CI (80% min)                  |
| JuniperData availability during training | Medium     | Low    | Circuit breaker (CAN-MED-008) with graceful degradation  |

---

## Document History

| Date       | Author   | Changes                                                                                                                                                 |
| ---------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-02-17 | AI Agent | Initial creation from JuniperData codebase audit                                                                                                        |
| 2026-02-17 | AI Agent | Comprehensive rewrite: full notes/ audit, codebase validation, prioritization, and design analysis. Expanded from 28 items to 55 items across 5 phases. |
| 2026-02-25 | AI Agent | Codebase re-validation: Updated all `cascor_integration.py`/`CascorIntegration` refs to `cascor_service_adapter.py`/`CascorServiceAdapter` (post-polyrepo migration). Fixed summary table arithmetic (Phase 0 NS 1→2, Phase 2 NS 11→12, Grand Total NS 42→44, Complete 10→0). Corrected MyPy disabled code counts (3→7 remaining). Fixed stale line refs (CAN-CRIT-001 :871→:822, INT-CRIT-001 :487-530→:420-463, INT-CRIT-003 :1122-1159→:234). Removed non-existent `fit_async()` refs, fixed CAN-HIGH-007 test file list, normalized CAN-MED-014 priority to MEDIUM. Minor formatting fixes. |
