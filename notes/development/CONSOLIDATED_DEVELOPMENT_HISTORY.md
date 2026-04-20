# Juniper Canopy — Consolidated Development History

**Generated**: 2026-04-17
**Source Documents**: 16 files in `notes/development/` (13 readable, 3 broken symlinks)
**Scope**: All documented development work for juniper-canopy
**Validation**: Cross-referenced against codebase HEAD as of 2026-04-17

---

## Table of Contents

1. [Document Inventory](#1-document-inventory)
2. [Feature Development — Phases 0-3](#2-feature-development--phases-0-3)
3. [Canopy↔CasCor Connection Analysis](#3-canopycascor-connection-analysis)
4. [Demo Training Algorithm Analysis](#4-demo-training-algorithm-analysis)
5. [Meta Parameters Enhancement](#5-meta-parameters-enhancement)
6. [Post-Release Development Roadmap](#6-post-release-development-roadmap)
7. [Code Review and R5-01 Alignment](#7-code-review-and-r5-01-alignment)
8. [CI/CD and Infrastructure](#8-cicd-and-infrastructure)
9. [Codebase Validation Results](#9-codebase-validation-results)
10. [Current Status Summary](#10-current-status-summary)
11. [Broken Symlinks](#11-broken-symlinks)

---

## 1. Document Inventory

| #  | Document                                                      | Date       | Version | Theme                                  | Status                                     |
|----|---------------------------------------------------------------|------------|---------|----------------------------------------|--------------------------------------------|
| 1  | `DEVELOPMENT_ROADMAP.md`                                      | 2026-01-09 | 2.8.0   | Phase 0-3 feature/fix roadmap          | All items ✅ Done                          |
| 2  | `IMPLEMENTATION_PLAN.md`                                      | 2025-12-12 | 1.0.0   | Detailed implementation specs          | Complete (historical)                      |
| 3  | `JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md`          | 2026-02-17 | —       | Post-release comprehensive audit       | SUPERSEDED (sprints complete 2026-04-01)   |
| 4  | `FINAL_CANOPY_CASCOR_CONNECTION_ANALYSIS.md`                  | 2026-03-28 | 1.0.0   | Canopy↔CasCor connection failures      | Final synthesis — implementation reference |
| 5  | `META_PARAMETERS_ENHANCEMENT_PLAN.md`                         | 2026-03-21 | —       | Meta Parameters restructure            | Planning → Implemented                     |
| 6  | `ROOT_CAUSE_CANDIDATE_QUALITY_DEGRADATION.md`                 | 2026-03-19 | —       | Candidate quality degradation analysis | Proposal → Fixes applied                   |
| 7  | `ROOT_CAUSE_PROPOSAL_TRAINING_STALL.md`                       | 2026-03-19 | —       | Demo training stall analysis           | Proposal → Fixes applied                   |
| 8  | `ROOT_CAUSE_SPIRAL_COMPLEXITY.md`                             | 2026-03-19 | —       | Spiral dataset complexity analysis     | Proposal → Fix applied                     |
| 9  | `REMEDIATION_PLAN_CI_OBSERVABILITY_2026-04-04.md`             | 2026-04-04 | —       | CI observability deps fix              | Implemented and Verified                   |
| 10 | `CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md`            | 2026-04-12 | 0.4.0   | 99+ issues re-evaluated vs R5-01       | Active reference                           |
| 11 | `CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md`          | 2026-04-12 | 0.4.0   | 34 audit gaps re-evaluated             | Active reference                           |
| 12 | `CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md`                | 2026-04-12 | 0.4.0   | 4-track remediation plan               | Active reference                           |
| 13 | `CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md` | 2026-04-12 | 0.4.0   | Timeline + R5-01 coordination          | Active reference                           |
| 14 | `DASHBOARD_AUGMENTATION_PLAN.md`                              | —          | —       | Dashboard augmentation                 | ⚠️ Broken symlink                          |
| 15 | `DATASET_DISPLAY_FAILURE_ANALYSIS.md`                         | —          | —       | Dataset display failure                | ⚠️ Broken symlink                          |
| 16 | `DATASET_DISPLAY_FIX_PLAN.md`                                 | —          | —       | Dataset display fix                    | ⚠️ Broken symlink                          |

---

## 2. Feature Development — Phases 0-3

*Source: DEVELOPMENT_ROADMAP.md, IMPLEMENTATION_PLAN.md*:

### Phase 0: Core UX Stabilization (P0) — All Complete

| ID   | Feature/Fix                                                                        | Files                   | Validated                                                                      |
|------|------------------------------------------------------------------------------------|-------------------------|--------------------------------------------------------------------------------|
| P0-1 | Training Controls button state fix — buttons stay pressed, become unclickable      | `dashboard_manager.py`  | ✅ Implemented — button-states store, clientside callbacks, optimistic UI      |
| P0-2 | Meta-Parameters Apply Button — manual apply for parameter changes                  | `dashboard_manager.py`  | ✅ Implemented — `apply-params-button` with enable/disable callback            |
| P0-3 | Top Status Bar Status/Phase Updates — Status always "Stopped", Phase always "Idle" | `dashboard_manager.py`  | ✅ Implemented — unified status bar with `_build_unified_status_bar_content()` |
| P0-4 | Training Metrics Graph Range Persistence — range resets after ~1 second            | `metrics_panel.py`      | ✅ Implemented — `view-state` dcc.Store, `relayoutData` capture                |
| P0-5 | Network Topology Pan/Lasso Tool Fix — all tools perform Box Select                 | `network_visualizer.py` | ✅ Implemented — modeBar buttons, `dragmode="pan"`                             |
| P0-6 | Network Topology Interaction Persistence — interactions reset after ~1 second      | `network_visualizer.py` | ✅ Implemented — view-state store with axis ranges, dragmode                   |
| P0-7 | Network Topology Dark Mode Info Bar — white text on white background               | `network_visualizer.py` | ✅ Implemented — `_update_stats_bar_theme` with dark/light toggle              |

### Phase 1: High-Impact Enhancements (P1) — All Complete

| ID   | Feature                                              | Files                        | Validated                                                        |
|------|------------------------------------------------------|------------------------------|------------------------------------------------------------------|
| P1-1 | Candidate Node Info Section — display/collapsibility | `candidate_metrics_panel.py` | ✅ Implemented — dedicated `CandidateMetricsPanel` class         |
| P1-2 | Network Topology Staggered Layout                    | `network_visualizer.py`      | ✅ Implemented — `_layout_type_staggered()`, position offsets    |
| P1-3 | Training Metrics Replay Functionality                | `metrics_panel.py`           | ✅ Implemented — full replay controls, slider, position tracking |
| P1-4 | Node Selection Interactions                          | `network_visualizer.py`      | ✅ Implemented — clickData + selectedData handling               |

### Phase 2: Polish Features (P2) — All Complete

| ID   | Feature                                                   | Files                     | Validated                                                     |
|------|-----------------------------------------------------------|---------------------------|---------------------------------------------------------------|
| P2-1 | Most Recently Added Node Indicator — glow/pulse animation | `network_visualizer.py`   | ✅ Implemented — new-node-highlight store, yellow glow traces |
| P2-2 | Unique Image Download Names — timestamp-based             | `network_visualizer.py`   | ✅ Implemented — `canopy_network_{datetime}` filename         |
| P2-3 | About Tab                                                 | `about_panel.py`          | ✅ Implemented — version, license, credits, links             |
| P2-4 | HDF5 Snapshot Tab (read-only)                             | `hdf5_snapshots_panel.py` | ✅ Implemented — list, refresh, detail view                   |

### Phase 3: Advanced Features (P3) — All Complete

| ID   | Feature                     | Files                     | Validated                                            |
|------|-----------------------------|---------------------------|------------------------------------------------------|
| P3-1 | Training Metrics Save/Load  | `metrics_panel.py`        | ✅ Implemented — save/load layout controls           |
| P3-2 | Network Topology 3D View    | `network_visualizer.py`   | ✅ Implemented — `go.Scatter3d`, 2D/3D toggle        |
| P3-3 | Cassandra Integration Tab   | `cassandra_panel.py`      | ✅ Implemented — status, cluster, schema overview    |
| P3-4 | Redis Integration Tab       | `redis_panel.py`          | ✅ Implemented — status, health, performance metrics |
| P3-5 | HDF5 Create/Restore/History | `hdf5_snapshots_panel.py` | ✅ Implemented — create, restore modal, history      |

---

## 3. Canopy↔CasCor Connection Analysis

*Source: FINAL_CANOPY_CASCOR_CONNECTION_ANALYSIS.md (2026-03-28)*:

### Phase 1 Assessment

All **14 Phase 1 fixes** (FIX-1 through FIX-13 + FIX-SYS) correctly implemented:

- ResponseEnvelope unwrapping working
- Falsy-value preservation (epoch=0, loss=0.0) working
- Field normalization improved
- **Critical oversight**: Phase 1 flat contract never validated against dashboard's nested format

### Root Cause Registry (20 entries)

| ID           | Severity         | Summary                                                      | Validated                                                                   |
|--------------|------------------|--------------------------------------------------------------|-----------------------------------------------------------------------------|
| **P5-RC-01** | **CRITICAL**     | Metrics format mismatch — flat service vs nested dashboard   | ✅ FIXED — `_to_dashboard_metric()` at `cascor_service_adapter.py:804`      |
| **P5-RC-02** | **CRITICAL**     | Topology format mismatch — weight-oriented vs graph-oriented | ✅ FIXED — `_transform_topology()` at `cascor_service_adapter.py:852`       |
| **P5-RC-03** | HIGH (latent)    | Uppercase status normalization gap in relay path             | ✅ FIXED — `.lower()` in `state_sync.py:71,74` and `service_backend.py:130` |
| P5-RC-04     | MODERATE         | WebSocket relay state callback only forwards status + phase  | Not validated                                                               |
| P5-RC-05     | LOW              | Dashboard ignores WebSocket relay, polls via HTTP only       | Partially resolved — WS bridge exists but REST fallback remains             |
| P5-RC-06     | MODERATE         | CasCor `TrainingMonitor.current_phase` never updated         | Cross-repo (juniper-cascor)                                                 |
| P5-RC-07     | MODERATE         | State sync stores metrics history without normalization      | Not validated                                                               |
| P5-RC-08     | MODERATE         | State sync bypasses adapter normalization                    | Not validated                                                               |
| P5-RC-09     | MODERATE         | `/api/metrics` current snapshot also flat format             | Fixed via P5-RC-01 fix (same `_to_dashboard_metric()`)                      |
| P5-RC-10     | MODERATE         | State sync params stored in raw CasCor namespace             | Not validated                                                               |
| **P5-RC-11** | MODERATE         | Hardcoded `localhost:8050` URLs (6 instances)                | ✅ FIXED — zero `localhost:8050` in source                                  |
| P5-RC-12     | LOW              | `cn_training_iterations` → `candidate_epochs` non-functional | Not validated                                                               |
| P5-RC-12b    | LOW              | `patience` mapped to wrong semantic field                    | Not validated                                                               |
| P5-RC-13     | LOW              | `candidate_learning_rate` unmapped in Canopy                 | Not validated                                                               |
| P5-RC-14     | LOW              | WebSocket relay broadcasts unnormalized metrics              | Not validated                                                               |
| P5-RC-15     | LOW              | Double initialization on fallback-to-demo path               | Not validated                                                               |
| P5-RC-16     | LOW              | Phase 1 tests validate flat output, not dashboard compat     | Not validated                                                               |
| P5-RC-17     | INFO             | Dual status normalization paths inconsistent                 | Not validated                                                               |
| **P5-RC-18** | SYSTEMIC         | No canonical backend contract across demo/service modes      | Structural — partially addressed by `_to_dashboard_metric()`                |
| **KL-1**     | Known Limitation | Dataset scatter plot empty in service mode                   | Architectural limitation                                                    |

### Verified Working Paths

| Subsystem                                           | Status     |
|-----------------------------------------------------|------------|
| Status bar (is_running, phase, epoch, hidden units) | ✅ Working |
| Decision boundary visualization                     | ✅ Working |
| Dataset metadata display                            | ✅ Working |
| Training controls (start/stop/pause/resume/reset)   | ✅ Working |
| Parameter updates (apply_params write path)         | ✅ Working |
| WebSocket relay connection/broadcast                | ✅ Working |
| ResponseEnvelope unwrapping                         | ✅ Working |
| Non-destructive attach to running CasCor            | ✅ Working |

---

## 4. Demo Training Algorithm Analysis

*Source: ROOT_CAUSE_CANDIDATE_QUALITY_DEGRADATION.md, ROOT_CAUSE_PROPOSAL_TRAINING_STALL.md, ROOT_CAUSE_SPIRAL_COMPLEXITY.md (all 2026-03-19)*:

### Identified Root Causes

**Candidate Quality Degradation** (5 sub-causes):

1. Pool size too small (8 vs 50 in reference)
2. Fixed 200 steps insufficient, no convergence check
3. Pearson correlation gradient degradation
4. Weight initialization scale mismatch
5. Epsilon placement difference

**Training Stall** (5 algorithmic mismatches):

1. Interleaved single-step vs phase-based convergence
2. Warm-start vs random reset output weights
3. Loss stagnation vs correlation threshold cascade trigger
4. Stale residual error computation
5. Artificial loss manipulation corrupts convergence signal

**Spiral Complexity**: 3-rotation spiral too complex for demo training budget

### Fix Validation

| Fix                                       | Proposed                | Validated                                                            |
|-------------------------------------------|-------------------------|----------------------------------------------------------------------|
| Reduce spiral rotations to 1.0            | 1.0 proposed            | ✅ Changed to **1.5** (improved from 3.0) — `canopy_constants.py:88` |
| Increase candidate pool size to 16+       | 16+ proposed            | ✅ **32** — `canopy_constants.py:141`                                |
| Increase candidate training steps to 400+ | 400+ proposed           | ✅ **600** — `canopy_constants.py:142`                               |
| Add early stopping (patience=30)          | Proposed                | ✅ Implemented — `demo_mode.py:426-458`, `CANDIDATE_PATIENCE=30`     |
| Multi-step output training per epoch      | 50 steps/epoch          | ✅ Implemented — `OUTPUT_RETRAIN_STEPS=1000`, emit every 50          |
| Remove artificial loss manipulation       | Remove `*1.5` / `*0.8`  | ✅ Removed — no artificial manipulation in codebase                  |
| Correlation-based cascade trigger         | Replace loss stagnation | ✅ Implemented — `train_candidate_pool()` with correlation threshold |

---

## 5. Meta Parameters Enhancement

*Source: META_PARAMETERS_ENHANCEMENT_PLAN.md (2026-03-21)*:

### Summary

Restructured Training Parameters → Meta Parameters with two subsections:

- **Neural Network** (12 inputs): max iterations, total epochs, learning rate, max hidden units, multi-node layers, growth trigger radio, preset epochs, convergence threshold, spiral rotations, spiral number, dataset elements, dataset noise
- **Candidate Nodes** (10 inputs): pool size, correlation threshold, selected candidates, training complete radio, training iterations, convergence threshold, multi-candidate selection, selection radio, top/random candidate counts

### Validation

✅ **Fully implemented** — `nn-learning-rate-input`, `cn-pool-size-input`, subsection collapse components, toggle callbacks all present in `dashboard_manager.py`.

---

## 6. Post-Release Development Roadmap

*Source: JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md (2026-02-17, updated 2026-04-05)*:

### Critical Items

| ID           | Item                               | Status             | Validated                                                                               |
|--------------|------------------------------------|--------------------|-----------------------------------------------------------------------------------------|
| CAN-CRIT-001 | Decision Boundary for Real Backend | PARTIALLY RESOLVED | ✅ Confirmed — `/api/decision_boundary` endpoint + `get_decision_boundary()` in adapter |
| CAN-CRIT-002 | Save/Load Snapshot in Adapter      | SCOPE REDUCED      | ✅ Confirmed — `save_snapshot()` + `load_snapshot()` delegate to client                 |

### High Priority Items

| ID           | Item                              | Status                 | Validated                                              |
|--------------|-----------------------------------|------------------------|--------------------------------------------------------|
| CAN-HIGH-001 | Startup Health Check              | COMPLETE               | ✅ Confirmed — `probe_dependency()` in lifespan        |
| CAN-HIGH-002 | NPZ Validation                    | PARTIALLY IMPLEMENTED  | ⚠️ Partial — `_validate_npz_arrays()` only in DemoMode |
| CAN-HIGH-003 | Async/Sync Boundary Testing       | SCOPE CHANGED          | Not validated                                          |
| CAN-HIGH-004 | Real Backend Path Tests           | PARTIALLY ADDRESSED    | Not validated                                          |
| CAN-HIGH-005 | Remote Worker Status              | SCOPE CHANGED → MEDIUM | Not validated                                          |
| CAN-HIGH-006 | JuniperData Error Handling        | NOT STARTED            | Not validated                                          |
| CAN-HIGH-007 | Convert Skipped Integration Tests | PARTIALLY ADDRESSED    | Not validated                                          |

### Polyrepo Migration (2026-02-25)

| Aspect              | Before                                | After                                                 |
|---------------------|---------------------------------------|-------------------------------------------------------|
| Backend integration | `cascor_integration.py` (1,601 lines) | `cascor_service_adapter.py` (1,154 lines — validated) |
| Communication       | Direct Python imports                 | REST/WebSocket via client libraries                   |
| Data access         | Direct file I/O                       | HTTP via juniper-data-client                          |
| Activation modes    | Demo, Legacy, Service                 | Demo, Service (with fallback)                         |
| Testing             | 163 tests                             | 4,531 test functions (validated)                      |

### Enhancement Backlog (23 items: CAN-001 through CAN-023)

Dashboard features including: time window selection, custom ranges, parameter tuning tabs, pin/unpin parameters, individual parameter controls (CAN-006 through CAN-013), snapshot capture/replay, layout persistence, tooltips/tutorials, hierarchy/population selection.

---

## 7. Code Review and R5-01 Alignment

*Source: 4 CODE_REVIEW documents (all 2026-04-12, v0.4.0)*:

### Issue Summary (99+ issues)

| Severity | Total | REAFFIRMED | SUPERSEDED | DEFERRED | COORDINATED | MODIFIED |
|----------|-------|------------|------------|----------|-------------|----------|
| Critical | 3     | 3          | 0          | 0        | 0           | 0        |
| High     | 19    | 15         | 1          | 1        | 2           | 0        |
| Medium   | 47    | 40         | 0          | 1        | 5           | 1        |
| Low      | 30+   | 30+        | 0          | 0        | 0           | 0        |

### Critical Issues — Validation

| ID       | Description                          | R5-01 Category | Validated                                                                   |
|----------|--------------------------------------|----------------|-----------------------------------------------------------------------------|
| CRIT-001 | Path Traversal in Snapshot Endpoints | REAFFIRMED     | ✅ FIXED — `_sanitize_snapshot_name()` regex + `Path.resolve()` confinement |
| CRIT-002 | Thread-Unsafe CallbackContextAdapter | REAFFIRMED     | ✅ FIXED — `contextvars.ContextVar` in `callback_context.py`                |
| CRIT-003 | Lockfile Extras Mismatch             | REAFFIRMED     | ✅ FIXED — `requirements.lock` includes `--extra observability`             |

### High Issues — Validation

| ID       | Description                                | R5-01 Category | Validated                                                         |
|----------|--------------------------------------------|----------------|-------------------------------------------------------------------|
| HIGH-001 | API Key Timing Attack                      | REAFFIRMED     | ✅ FIXED — `hmac.compare_digest` in `security.py`                 |
| HIGH-002 | Exception Handler Leaks Internal Details   | REAFFIRMED     | ✅ FIXED — generic `ErrorResponse`                                |
| HIGH-003 | Rate Limiter Memory Leak                   | REAFFIRMED     | ✅ FIXED — `_evict_expired()`, emergency cap                      |
| HIGH-004 | threading.Event Replacement Race           | REAFFIRMED     | ⚠️ NOT FIXED — `_stop.clear()` outside lock in `_perform_reset()` |
| HIGH-005 | Synchronous Blocking HTTP                  | **SUPERSEDED** | ✅ Band-aid timeout retained; R5-01 Phase B canonical fix         |
| HIGH-006 | _api_url() Uses Flask Request Context      | REAFFIRMED     | ✅ FIXED — settings-based URL                                     |
| HIGH-007 | NetworkVisualizer Screenshot Filename      | REAFFIRMED     | ✅ FIXED — timestamp-based filename                               |
| HIGH-008 | Debug Mode in Docker                       | REAFFIRMED     | ✅ FIXED — production defaults in Dockerfile                      |
| HIGH-009 | Bandit Config Fragmentation                | REAFFIRMED     | ✅ FIXED — consolidated `.bandit.yml`                             |
| HIGH-010 | WebSocket /ws Silent Exception Loop        | COORDINATED    | ✅ FIXED — `finally` block cleanup                                |
| HIGH-011 | Hardcoded Version Strings                  | REAFFIRMED     | ✅ FIXED — `importlib.metadata.version`                           |
| HIGH-013 | Duplicate Phase Band/Marker Logic          | REAFFIRMED     | ✅ FIXED — shared `_add_phase_bg_bands()`                         |
| HIGH-014 | DashboardManager God Class (3007 lines)    | **DEFERRED**   | ⚠️ NOT FIXED — still **3,232 lines** (increased)                  |
| HIGH-015 | TrainingStateMachine No Thread Safety      | REAFFIRMED     | ✅ FIXED — `threading.Lock` on all methods                        |
| HIGH-016 | False Positive Tests (contextlib.suppress) | REAFFIRMED     | ✅ FIXED — zero occurrences in tests                              |
| HIGH-017 | WebSocket Schema Tests No Fail Guard       | COORDINATED    | ✅ FIXED — `pytest.fail()` guards                                 |
| HIGH-018 | hasattr Guards Skip Test Logic             | REAFFIRMED     | ⚠️ NOT FIXED — 100+ `hasattr` guards remain                       |
| HIGH-019 | Performance Test No-Op                     | REAFFIRMED     | ⚠️ PARTIALLY FIXED — 1 real test, minimal suite                   |

### R5-01 Phase Infrastructure — Validation

| Item                       | Expected                            | Validated                                           |
|----------------------------|-------------------------------------|-----------------------------------------------------|
| `theme_constants.py`       | Infrastructure ready (POST MED-026) | ✅ Exists — 1,502 bytes                             |
| `ws_security.py`           | Phase B-pre-a                       | ✅ Exists — 39 lines                                |
| `audit_log.py`             | Phase B-pre-a                       | ✅ Exists — 114 lines                               |
| `ws_dash_bridge.js`        | Phase B                             | ✅ Exists — 117 lines                               |
| `connection_indicator.py`  | Phase B                             | ✅ Exists — 84 lines                                |
| `csrf.py`                  | Phase B-pre-b                       | ✅ Exists — CSRF token store + `/api/csrf` endpoint |
| Per-IP connection cap      | Phase B-pre-a                       | ✅ Implemented — `max_connections_per_ip: 5`        |
| `_pending_connections`     | Phase 0-cascor                      | ✅ Not implemented (correctly deferred)             |
| Polling toggle (WS bridge) | Phase B                             | ✅ Partial — hybrid REST+WS approach                |

### 4-Track Remediation Structure

| Track    | Scope                                      | Status                                     |
|----------|--------------------------------------------|--------------------------------------------|
| **PRE**  | Independent security, concurrency, CI/CD   | ~95% complete via PR #146                  |
| **PAR**  | Test quality, logging, observability       | ~93% complete via PR #146                  |
| **EMB**  | R5-01 phase-embedded fixes (7 coordinated) | Partially implemented (ahead of schedule)  |
| **POST** | Architecture refactors, conf/Dockerfile    | Not started (blocked by Phase B stability) |

### 20 New R5-01 Requirements

R5-01-NEW-001 through R5-01-NEW-020 covering: server_instance_id, replay_buffer_capacity, seq fields, emitted_at_monotonic, command_id echo, two-phase registration, resume protocol, CSRF auth, HMAC auth, origin allowlist, per-IP cap, frame size cap, rate limiting, heartbeat, per-command timeouts, drain callbacks, polling elimination, connection indicator, CSRF endpoint, latency beacon.

---

## 8. CI/CD and Infrastructure

*Source: REMEDIATION_PLAN_CI_OBSERVABILITY_2026-04-04.md*:

### CI Observability Fix

| Item    | Details                                                      | Validated                          |
|---------|--------------------------------------------------------------|------------------------------------|
| Problem | 5 unit tests fail — undeclared sentry_sdk, prometheus_client | ✅ Fixed                           |
| Fix     | Added `observability` extra to `pyproject.toml`              | ✅ Confirmed                       |
| Updated | `requirements.lock`, CI lockfile check                       | ✅ Confirmed                       |
| Result  | 4,169 tests passed, 56 skipped                               | Superseded by 4,531 test functions |

---

## 9. Codebase Validation Results

### Validation Summary

| Category                  | Total Checked | Fixed | Partially Fixed | Not Fixed | Not Validated |
|---------------------------|---------------|-------|-----------------|-----------|---------------|
| Critical Issues (CRIT)    | 3             | 3     | 0               | 0         | 0             |
| High Issues (HIGH)        | 18            | 13    | 1               | 3         | 1             |
| Connection Issues (P5-RC) | 5             | 4     | 1               | 0         | 0             |
| Phase 0-3 Features        | 20            | 20    | 0               | 0         | 0             |
| Demo Training Fixes       | 7             | 7     | 0               | 0         | 0             |
| Meta Parameters           | 1             | 1     | 0               | 0         | 0             |
| Post-Release Items        | 5             | 3     | 2               | 0         | 0             |
| R5-01 Infrastructure      | 9             | 8     | 1               | 0         | 0             |

### Outstanding Issues (Not Fixed)

| ID       | Description                          | Priority | Reason                                              |
|----------|--------------------------------------|----------|-----------------------------------------------------|
| HIGH-004 | threading.Event `_stop.clear()` race | HIGH     | Second call site in `_perform_reset()` outside lock |
| HIGH-014 | DashboardManager God Class           | HIGH     | Now 3,232 lines (deferred to post-R5-01 Phase B)    |
| HIGH-018 | hasattr Guards in Tests              | HIGH     | 100+ guards still silently skip test logic          |

### Codebase Metrics

| Metric                            | Value                                                                                                                                             |
|-----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| `dashboard_manager.py` lines      | 3,232                                                                                                                                             |
| `cascor_service_adapter.py` lines | 1,154                                                                                                                                             |
| Test files                        | 188                                                                                                                                               |
| Test functions                    | 4,531                                                                                                                                             |
| Frontend components               | about_panel, candidate_metrics_panel, cassandra_panel, connection_indicator, hdf5_snapshots_panel, metrics_panel, network_visualizer, redis_panel |

---

## 10. Current Status Summary

### What's Done

- ✅ All Phase 0-3 features (20 items) — fully implemented and validated
- ✅ Canopy↔CasCor critical connection fixes (P5-RC-01, P5-RC-02) — metrics + topology transformation
- ✅ Demo training algorithm fixes — pool size, steps, early stopping, cascade trigger, loss manipulation removed
- ✅ Meta Parameters enhancement — full 22-input restructure
- ✅ Code review Track PRE (~95%) and Track PAR (~93%) via PR #146
- ✅ CI observability dependency fix
- ✅ R5-01 Phase B-pre-a/b infrastructure (ws_security, audit_log, csrf, per-IP caps)
- ✅ R5-01 Phase B infrastructure (ws_dash_bridge.js, connection_indicator, polling toggle)

### What's In Progress

- ⏳ R5-01 Phase B polling elimination (hybrid REST+WS, not fully eliminated)
- ⏳ Track EMB embedded fixes (partially ahead of schedule)

### What's Deferred

- 🔜 HIGH-014: DashboardManager extraction (blocked by R5-01 Phase B stability)
- 🔜 MED-026: ThemeColors rollout (infra ready, rollout deferred)
- 🔜 conf/Dockerfile alignment (POST-2, pending ops decision)
- 🔜 LOW-003, LOW-007: Minor completions

### What's Not Fixed

- ❌ HIGH-004: `_stop.clear()` race in `_perform_reset()` (outside lock)
- ❌ HIGH-018: 100+ `hasattr` guards in test files
- ❌ HIGH-014: God class at 3,232 lines (deferred, not fixed)

---

## 11. Broken Symlinks

Three files in `notes/development/` are broken symlinks whose targets no longer exist:

| File                                  | Target                                                                      | Status            |
|---------------------------------------|-----------------------------------------------------------------------------|-------------------|
| `DASHBOARD_AUGMENTATION_PLAN.md`      | `../../../juniper-ml/notes/DASHBOARD_AUGMENTATION_PLAN.md`                  | ⚠️ Target missing |
| `DATASET_DISPLAY_FAILURE_ANALYSIS.md` | `../../../juniper-ml/notes/development/DATASET_DISPLAY_FAILURE_ANALYSIS.md` | ⚠️ Target missing |
| `DATASET_DISPLAY_FIX_PLAN.md`         | `../../../juniper-ml/notes/development/DATASET_DISPLAY_FIX_PLAN.md`         | ⚠️ Target missing |

These symlinks reference files in the juniper-ml repository that have been moved or deleted. Their content is not included in this consolidation.

---

*Document generated: 2026-04-17*
*Validation: Automated codebase cross-reference against HEAD*
*Source: 13 readable documents + 3 broken symlinks in `juniper-canopy/notes/development/`*
