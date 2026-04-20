# Phase 5: Comprehensive Canopy-CasCor Connection Analysis — Consolidated Synthesis

- **Version**: 1.0.0
- **Date**: 2026-03-28
- **Author**: Amp (AI Agent) — Phase 5 Synthesis
- **Status**: Analysis Complete — Synthesized, Validated, Finalized
- **UUID**: 7f73219c-1557-4135-ab44-ef053d4c4097
- **Source Material**: 4 independent Phase 4 proposals, 7 Phase 3 proposals, Phase 1 development plan, Phase 2 root cause analysis
- **Repositories Analyzed**: juniper-canopy, juniper-cascor, juniper-cascor-client
- **Validation**: All findings independently verified against current codebase HEAD by specialized sub-agents

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Methodology](#2-methodology)
3. [Phase 4 Proposal Evaluation](#3-phase-4-proposal-evaluation)
4. [Phase 1 and Phase 2 Assessment](#4-phase-1-and-phase-2-assessment)
5. [Consolidated Root Cause Registry](#5-consolidated-root-cause-registry)
6. [Detailed Issue Analysis](#6-detailed-issue-analysis)
7. [Retracted / Rejected Issues](#7-retracted--rejected-issues)
8. [Cross-Proposal Agreement Matrix](#8-cross-proposal-agreement-matrix)
9. [Root Cause Dependency Graph](#9-root-cause-dependency-graph)
10. [Verified Working Subsystems](#10-verified-working-subsystems)
11. [Fix Recommendations](#11-fix-recommendations)
12. [Implementation Priority and Ordering](#12-implementation-priority-and-ordering)
13. [Risk Assessment](#13-risk-assessment)
14. [Verification Plan](#14-verification-plan)
15. [Files Requiring Modification](#15-files-requiring-modification)
16. [Post-Synthesis Validation Results](#16-post-synthesis-validation-results)
17. [Appendix A: Phase 4 Proposal Assessment](#appendix-a-phase-4-proposal-assessment)
18. [Appendix B: Document Lineage](#appendix-b-document-lineage)

---

## 1. Executive Summary

This Phase 5 analysis synthesizes, integrates, and validates findings from four independent Phase 4 proposals. Each Phase 4 proposal itself synthesized findings from seven independent Phase 3 proposals. All claims have been re-validated against the current codebase by specialized verification sub-agents.

### Key Finding

The juniper-canopy dashboard fails to display training metrics and network topology from an externally running juniper-cascor instance due to **data format mismatches at the "last mile"** — the boundary between the backend normalization layer and the dashboard's consumption layer. Phase 1's 14 ResponseEnvelope fixes are all correctly implemented, but they normalize to a **flat** format that the dashboard cannot consume. The dashboard was built against demo mode's **nested** format.

### Consolidated Root Cause Summary

| ID         | Severity     | Root Cause                                                                         | Phase 5 Validation                   | Display Blocker |
|------------|--------------|------------------------------------------------------------------------------------|--------------------------------------|-----------------|
| **RC-01**  | **CRITICAL** | Metrics format mismatch: flat keys vs nested keys                                  | **CONFIRMED**                        | **Yes**         |
| **RC-02**  | **CRITICAL** | Network topology format mismatch: weight-oriented vs graph-oriented                | **CONFIRMED**                        | **Yes**         |
| **RC-03**  | MODERATE     | WebSocket relay state callback omits fields (only sends status + phase)            | **CONFIRMED**                        | No              |
| **RC-04**  | MODERATE     | CasCor `TrainingMonitor.current_phase` never updated after init                    | **CONFIRMED**                        | No              |
| **RC-05**  | MODERATE     | State sync `metrics_history` stored raw without normalization                      | **CONFIRMED** (low practical impact) | No              |
| **RC-06**  | MODERATE     | Hardcoded `localhost:8050` URLs in MetricsPanel (6 instances)                      | **CONFIRMED**                        | No              |
| **RC-07**  | MODERATE     | Dataset scatter plot always empty in service mode                                  | **CONFIRMED**                        | No              |
| **RC-08**  | LOW          | WebSocket relay broadcasts unnormalized metric field names                         | **CONFIRMED**                        | No              |
| **RC-09**  | LOW          | `candidate_epochs` parameter mapping not runtime-updatable                         | **CONFIRMED** (reclassified)         | No              |
| **RC-10**  | LOW          | `candidate_learning_rate` updatable on CasCor but unmapped in Canopy               | **CONFIRMED**                        | No              |
| **RC-11**  | LOW          | Double initialization on fallback-to-demo path                                     | **CONFIRMED**                        | No              |
| **RC-12**  | LOW          | Dashboard ignores WebSocket relay, uses HTTP polling only                          | **CONFIRMED**                        | No              |
| **RC-13**  | LOW          | Phase 1 test coverage gap: tests validate flat output, not dashboard compatibility | **CONFIRMED**                        | No              |
| **RC-14**  | INFO         | Dual status normalization paths produce inconsistent representations               | **CONFIRMED**                        | No              |
| **RC-SYS** | SYSTEMIC     | No canonical backend contract — `BackendProtocol` returns `Dict[str, Any]`         | **CONFIRMED**                        | No              |

### Key Corrections from Phase 5 Validation

| Phase 4 Claim                                       | Phase 5 Verdict              | Correction                                                                                                                                                                                |
|-----------------------------------------------------|------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Uppercase status normalization gap is HIGH severity | **REFUTED**                  | CasCor sends title-case strings (e.g., `"Started"`), which `_normalize_status()` already handles. The gap is theoretical only — CasCor never sends uppercase enum names over WebSocket.   |
| State sync metrics history is a functional bug      | **CONFIRMED but low impact** | `metrics_history` in synced state has **no downstream consumer** — it is stored but never injected into the metrics panel or training monitor at startup.                                 |
| `candidate_epochs` mapping is "dead code"           | **Reclassified**             | `candidate_epochs` exists on `CascadeCorrelationConfig` but is NOT in `TrainingParamUpdateRequest`'s updatable fields. The mapping succeeds but the update is silently dropped by CasCor. |
| 2 hardcoded URLs in metrics_panel.py                | **Corrected to 6**           | Validation found 6 hardcoded `localhost:8050` URLs, not 2.                                                                                                                                |

**Bottom line**: Fixing RC-01 alone will restore metrics charts. Fixing RC-01 + RC-02 will restore full dashboard display. All other issues affect data freshness, correctness, deployment portability, or architectural quality but do not prevent the dashboard from displaying data.

---

## 2. Methodology

### 2.1 Phase 5 Synthesis Process

1. All 4 Phase 4 proposals were read in their entirety
2. Each proposal's issue catalog was extracted and cross-referenced against the other 3 proposals
3. Issues were deduplicated and merged — descriptions synthesized from all identifying proposals
4. Conflicting assessments between proposals were flagged for codebase verification
5. **Every claim was independently re-validated against the current source code** using 5 specialized sub-agents:
   - Agent 1: RC-01 (metrics format mismatch) — full data path trace
   - Agent 2: RC-02 (topology format mismatch) — full data path trace
   - Agent 3: RC-03, uppercase status (retracted), RC-05 (state sync) — relay and sync paths
   - Agent 4: RC-06, RC-09, RC-10, RC-11, RC-04 — miscellaneous issues
   - Agent 5: RC-SYS (backend protocol), RC-08, RC-07 — systemic and remaining issues
6. False positives were identified, documented, and removed from the active issue list
7. Severity assessments were re-evaluated based on validation results

### 2.2 Phase 4 Proposal Documents

| UUID       | Author          | Issues Cataloged                | Numbering                 |
|------------|-----------------|---------------------------------|---------------------------|
| `002192f3` | Amp             | 13 active (2 retracted)         | ISSUE-1 through ISSUE-13  |
| `66a019dc` | Claude Opus 4.6 | 16 active                       | P4-RC-01 through P4-RC-16 |
| `cd8254d3` | Amp             | 15 active (3 rejected/subsumed) | RC-1 through RC-15 + KL-1 |
| `d7dcbd5a` | Claude Opus 4.6 | 19 (17 issues + 2 systemic)     | ISS-01 through ISS-19     |

### 2.3 Repositories Examined

| Repository            | Key Files                                                                                                                                                                                                                                                            |
|-----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| juniper-canopy        | `cascor_service_adapter.py`, `service_backend.py`, `state_sync.py`, `main.py`, `metrics_panel.py`, `network_visualizer.py`, `dashboard_manager.py`, `demo_mode.py`, `demo_backend.py`, `protocol.py`, `data_adapter.py`, `dataset_plotter.py`, `training_monitor.py` |
| juniper-cascor        | `api/lifecycle/manager.py`, `api/lifecycle/monitor.py`, `api/lifecycle/state_machine.py`, `api/models/training.py`, `api/models/network.py`, `cascade_correlation_config.py`                                                                                         |
| juniper-cascor-client | `client.py`, `ws_client.py`, `testing/fake_client.py`, `testing/scenarios.py`                                                                                                                                                                                        |

---

## 3. Phase 4 Proposal Evaluation

### 3.1 Cross-Proposal Agreement

All 4 Phase 4 proposals **unanimously agree** on:

1. All 14 Phase 1 ResponseEnvelope fixes are correctly implemented
2. **RC-01 (metrics format mismatch) is the primary blocker** — all Phase 3 proposals (7/7) confirmed this
3. **RC-02 (topology format mismatch) is the secondary blocker** — identified by Phase 3 v2 and v4
4. The fix approach for RC-01: add `_to_dashboard_metric()` transformation after `_normalize_metric()`
5. Phase 2 was correct but too narrowly scoped — focused only on the metrics display path

### 3.2 Inter-Proposal Divergences Resolved

| Topic                      | Proposals' Positions                                                                                   | Phase 5 Resolution                                                                                                                                    |
|----------------------------|--------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Uppercase status severity  | `002192f3`: H; `66a019dc`: H; `cd8254d3`: M (latent); `d7dcbd5a`: H (latent)                           | **Removed as active issue** — Phase 5 validation proved CasCor never sends uppercase strings over WebSocket. Title-case is already handled.           |
| Number of hardcoded URLs   | `002192f3`: 6; `cd8254d3`: 2 (initially), 6 (post-validation); `66a019dc`: 6                           | **6 confirmed** — Phase 5 validation found 6 instances at lines 1000, 1021, 1155, 1187, 1231, 1274.                                                   |
| `candidate_epochs` mapping | `002192f3`: dead code; `66a019dc`: dead param map; `d7dcbd5a`: dead param                              | **Reclassified** — `candidate_epochs` in config object, not in runtime-updatable param set. Mapping execs but update is silently dropped.             |
| State sync metrics impact  | `002192f3`: M; `66a019dc`: M; `cd8254d3`: M; `d7dcbd5a`: M                                             | **MODERATE but low practical impact** — Phase 5 validation found `metrics_history` in synced state has no downstream consumer.                        |
| `/api/metrics` snapshot    | `66a019dc`: issue (P4-RC-09); `cd8254d3`: subsumed by RC-1; `d7dcbd5a`: ISS-07                         | **Subsumed by RC-01** — `get_current_metrics()` calls same `_normalize_metric()` ret same flat format. RC-01 fix applied here. not unique root cause. |
| Dataset empty scatter      | `002192f3`: ISSUE-9, L; `66a019dc`: P4-RC-08, M; `cd8254d3`: KL-1 (known limit); `d7dcbd5a`: ISS-09, M | **CONFIRMED as MODERATE** — architectural limit of CasCor API (returns metadata only, not data arrays). Requires CasCor API ext to resolve.           |

### 3.3 Proposal Quality Assessment

| Proposal UUID | Strengths                                                                                                                                        | Limitations                                                                                            |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| `002192f3`    | Clear issue numbering; explicit retraction of false positives; useful fix priority matrix                                                        | Over-categorized: 13 issues but some overlap; claimed uppercase status as HIGH without full validation |
| `66a019dc`    | Most comprehensive issue catalog (16); strong dependency graph; complete implementation ordering                                                 | Most verbose; some findings could have been consolidated                                               |
| `cd8254d3`    | Strongest self-validation: caught 3 false positives/subsumed items; clear known-limitation designation; best risk assessment                     | Initially underreported hardcoded URL count (corrected in validation)                                  |
| `d7dcbd5a`    | Deepest architectural analysis (ISS-17 systemic root cause); best evidence inventory (Appendix C); most unique findings (ISS-07, ISS-12, ISS-13) | Most granular numbering (19 items including sub-items like ISS-15b) creates complexity                 |

---

## 4. Phase 1 and Phase 2 Assessment

### 4.1 Phase 1: All Fixes Verified

**Unanimous across all 4 Phase 4 proposals**: All 14 fixes (FIX-1 through FIX-13, plus FIX-SYS) are correctly implemented. ResponseEnvelope unwrapping, field name normalization, and falsy-value preservation all function as designed.

**Where Phase 1 went wrong** (unanimous): The "Canonical Internal Contract" (Section 6.2) defined flat keys (`train_loss`, `train_accuracy`, `hidden_units`) by analyzing the normalization boundary (CasCor → canopy adapter). It was **never validated against the dashboard's actual input format**. The dashboard was built against demo mode's nested format (`metrics.loss`, `network_topology.hidden_units`). The status bar worked because it reads flat keys, creating false confidence.

### 4.2 Phase 2: Correct but Incomplete

| Phase 2 Finding                   | Status      | Phase 5 Notes                                                       |
|-----------------------------------|-------------|---------------------------------------------------------------------|
| RC-1: Metrics format mismatch     | **Correct** | Primary blocker — confirmed by all proposals at all phases          |
| RC-2: Relay callback omits fields | **Correct** | Impact overstated for status bar (uses fresh REST, not stale state) |
| RC-3: Dashboard ignores WebSocket | **Correct** | Low priority — polling at 1s is adequate for current needs          |

**Phase 2 gaps**: Did not examine topology path, parameter mapping, state sync normalization, deployment portability, cross-repo bugs, or architectural contract enforcement. These gaps account for 12+ additional root causes discovered in Phase 3.

---

## 5. Consolidated Root Cause Registry

### RC-01: Metrics Data Format Mismatch — Flat Keys vs Nested Keys [CRITICAL]

**Severity**: CRITICAL — Primary display blocker
**Identified by**: All 7 Phase 3 proposals (unanimous); all 4 Phase 4 proposals (unanimous)
**Phase 5 Validation**: ✅ **CONFIRMED** — All line numbers exact. Data flow produces flat keys reaching dashboard's nested-key readers.

The service backend's `_normalize_metric()` (`cascor_service_adapter.py:431-460`) produces metrics with flat keys. The dashboard's `MetricsPanel` (`metrics_panel.py`) reads metrics using nested dictionary access at 10 confirmed locations. Demo mode (`demo_mode.py:1162-1177`) produces the nested format the dashboard expects.

**Service mode output (flat)**:

```python
{"epoch": 5, "train_loss": 0.45, "train_accuracy": 0.82, "val_loss": 0.6, "val_accuracy": 0.65, "hidden_units": 3, "phase": "output", "timestamp": "..."}
```

**Dashboard expects (nested)**:

```python
{"epoch": 5, "metrics": {"loss": 0.45, "accuracy": 0.82, "val_loss": 0.6, "val_accuracy": 0.65}, "network_topology": {"hidden_units": 3}, "phase": "output", "timestamp": "..."}
```

**Dashboard nested-key access locations** (all in `metrics_panel.py`):

| Line | Access Pattern                                        | Component                      |
|------|-------------------------------------------------------|--------------------------------|
| 1091 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit count display      |
| 1120 | `.get("metrics", {}).get("loss", 0)`                  | Current loss value             |
| 1121 | `.get("metrics", {}).get("accuracy", 0)`              | Current accuracy value         |
| 1122 | `.get("network_topology", {}).get("hidden_units", 0)` | Current hidden units           |
| 1330 | `.get("metrics", {}).get("loss", 0)`                  | Loss plot data series          |
| 1449 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (loss)     |
| 1450 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (loss)     |
| 1499 | `.get("metrics", {}).get("accuracy", 0)`              | Accuracy plot data series      |
| 1561 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (accuracy) |
| 1562 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (accuracy) |

**Field name mapping (non-trivial)**:

| Flat Key (from `_normalize_metric`) | Required Nested Path (dashboard) | Notes                 |
|-------------------------------------|----------------------------------|-----------------------|
| `train_loss`                        | `metrics.loss`                   | Strip `train_` prefix |
| `train_accuracy`                    | `metrics.accuracy`               | Strip `train_` prefix |
| `val_loss`                          | `metrics.val_loss`               | Same name             |
| `val_accuracy`                      | `metrics.val_accuracy`           | Same name             |
| `hidden_units`                      | `network_topology.hidden_units`  | Move into nested dict |

**Impact**: Loss chart flat at 0, accuracy chart flat at 0, current loss/accuracy show "0.0000"/"0.00%", hidden unit count always 0, hidden unit markers never rendered.

**Also affected**: `get_current_metrics()` (`cascor_service_adapter.py:86-94`) calls the same `_normalize_metric()`, producing flat format. The `/api/metrics` current snapshot endpoint is affected by the same bug.

---

### RC-02: Network Topology Format Mismatch — Weight-Oriented vs Graph-Oriented [CRITICAL]

**Severity**: CRITICAL — Secondary display blocker
**Identified by**: Phase 3 v2, v4; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED** — All 6 structural mismatches verified. `extract_network_topology()` is a pure passthrough.

CasCor returns a weight-oriented topology structure (`manager.py:569-584`). The `NetworkVisualizer` expects a graph-oriented structure (`network_visualizer.py:83-88, 577-579, 1043-1045`). The `extract_network_topology()` method (`cascor_service_adapter.py:480-484`) calls `_unwrap_response()` which only strips the `{"data": ...}` envelope — zero transformation of topology structure.

**CasCor returns (weight-oriented)**:

```python
{"input_size": 2, "output_size": 1, "hidden_units": [{"id": 0, "weights": [...], "bias": 0.1, "activation": "sigmoid"}], "output_weights": [...], "output_bias": [...]}
```

**Dashboard expects (graph-oriented)**:

```python
{"input_units": 2, "output_units": 1, "hidden_units": 3, "nodes": [...], "connections": [{"from": "i0", "to": "h0", "weight": 0.5}]}
```

**Structural mismatches**:

| Aspect            | CasCor Returns                                 | Visualizer Expects                     |
|-------------------|------------------------------------------------|----------------------------------------|
| Input count key   | `input_size`                                   | `input_units`                          |
| Output count key  | `output_size`                                  | `output_units`                         |
| Hidden units type | Array of `{weights, bias, activation}` objects | **Integer** (count)                    |
| Connections       | Not present (implicit in weight arrays)        | `[{"from", "to", "weight"}]` edge list |
| Nodes             | Not present                                    | `[{"id", "type", "label"}]` node list  |

**Demo mode** (`demo_backend.py:129-169`) produces the correct graph-oriented format with `nodes`, `connections`, `input_units`, `output_units`, `hidden_units` (integer).

**Additional finding**: `FakeCascorClient` in `juniper-cascor-client/testing/scenarios.py:248-257` returns a **third** format (graph-oriented with `nodes`/`connections`/`layers` but using `input_size`/`output_size` keys), meaning service-mode integration tests using `FakeCascorClient` would not catch this mismatch either.

**Impact**: Network topology graph shows empty placeholder or errors in service mode.

---

### RC-03: WebSocket Relay State Callback Omits Fields [MODERATE]

**Severity**: MODERATE
**Identified by**: All 7 Phase 3 proposals; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

The relay callback (`cascor_service_adapter.py:222-223`) only forwards `status` and `phase`:

```python
self._state_update_callback(status=status, phase=data.get("phase", ""))
```

CasCor state messages contain 12+ fields (`status`, `phase`, `learning_rate`, `max_hidden_units`, `max_epochs`, `current_epoch`, `current_step`, `network_name`, `dataset_name`, `threshold_function`, `optimizer_name`, `timestamp`). All except `status` and `phase` are discarded.

**Validation nuance**: The full message IS broadcast to browser clients via `websocket_manager.broadcast()` at line 206. The data loss is only in the server-side `training_state` Python object. The status bar is NOT affected because it uses fresh REST calls.

**Impact**: `/api/state` endpoint returns stale `current_epoch`, `hidden_units`, etc. between REST polls.

---

### RC-04: CasCor TrainingMonitor.current_phase Never Updated [MODERATE]

**Severity**: MODERATE — Cross-repo issue
**Identified by**: Phase 3 v5 (unique discovery); all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

`TrainingMonitor.current_phase` is set to `"output"` once at `monitor.py:111` during `__init__` and never updated. No code anywhere assigns to `monitor.current_phase` after initialization. The lifecycle manager tracks phases via `TrainingState.update_state(phase=...)` (a separate object), but the monitor's `current_phase` is permanently stuck.

**Impact**: Every metric emitted via `on_epoch_end()` reports `phase: "output"` even during candidate training. Phase labels in the dashboard will be incorrect for candidate pool epochs.

---

### RC-05: State Sync Metrics History Stored Without Normalization [MODERATE]

**Severity**: MODERATE (low practical impact)
**Identified by**: Phase 3 v1, v3, v5, v6, v7; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED** — but with reduced practical impact

`state_sync.py:115-127` stores metrics history raw from the CasCor client without applying `_normalize_metric()` or any equivalent transform. However, Phase 5 validation found that `SyncedState.metrics_history` is stored but **never consumed at startup** — `main.py` lines 190-200 only extract `status`, `phase`, `current_epoch`, `max_epochs`, `learning_rate`, and `max_hidden_units` from the synced state.

**Impact**: Latent bug — if any future code consumes `synced_state.metrics_history`, it will receive raw CasCor field names. Currently has no active downstream effect.

---

### RC-06: Hardcoded localhost:8050 URLs in MetricsPanel [MODERATE]

**Severity**: MODERATE
**Identified by**: Phase 3 v4; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED** — 6 instances (corrected from some proposals' claim of 2)

**Hardcoded URLs** (all in `metrics_panel.py`):

| Line | URL                                                          |
|------|--------------------------------------------------------------|
| 1000 | `http://localhost:8050/api/network/stats`                    |
| 1021 | `http://localhost:8050/api/state`                            |
| 1155 | `http://localhost:8050/api/v1/metrics/layouts`               |
| 1187 | `http://localhost:8050/api/v1/metrics/layouts`               |
| 1231 | `http://localhost:8050/api/v1/metrics/layouts/{layout_name}` |
| 1274 | `http://localhost:8050/api/v1/metrics/layouts/{layout_name}` |

**Impact**: Dashboard breaks in any deployment where Canopy is not at `localhost:8050` (e.g., Docker, remote server).

---

### RC-07: Dataset Scatter Plot Always Empty in Service Mode [MODERATE]

**Severity**: MODERATE — Architectural limitation
**Identified by**: Phase 3 v4; 3 of 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

CasCor's `/v1/dataset` endpoint (`manager.py:499-509`) returns metadata only (`loaded`, `train_samples`, `test_samples`, `input_features`, `output_features`). `ServiceBackend.get_dataset()` maps this to `num_samples`, `num_features`, `num_classes` — no `inputs` or `targets` arrays. `dataset_plotter._create_scatter_plot()` (`dataset_plotter.py:304-308`) expects `inputs` and `targets` arrays and shows "No data available" when they are absent.

**Impact**: Dataset scatter plot always shows "No data available" in service mode. Requires CasCor API extension or direct juniper-data integration to resolve.

---

### RC-08: WebSocket Relay Broadcasts Unnormalized Metric Field Names [LOW]

**Severity**: LOW — Latent; only becomes relevant if WebSocket consumption is implemented (RC-12)
**Identified by**: Phase 3 v4, v7; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

The relay loop (`cascor_service_adapter.py:203-206`) broadcasts raw CasCor payloads to browser clients with zero normalization. CasCor field names (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`) are forwarded verbatim.

**Impact**: Future blocker for WebSocket-based dashboard consumption. Currently mitigated by HTTP polling.

---

### RC-09: candidate_epochs Parameter Mapping Not Runtime-Updatable [LOW]

**Severity**: LOW
**Identified by**: Phase 3 v2, v4; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED** (reclassified from "dead code")

The mapping `"cn_training_iterations": "candidate_epochs"` (`cascor_service_adapter.py:364`) maps and sends the value, but `candidate_epochs` is NOT in `TrainingParamUpdateRequest` (`api/models/training.py:45-54`) and is NOT in the `updatable_keys` set (`manager.py:545-553`). The mapping executes successfully but the update is silently dropped by CasCor.

**Additional finding (Phase 3 v2)**: The `patience` → `nn_growth_convergence_threshold` mapping has a semantic mismatch — `patience` in deep learning typically means "epochs to wait before early stopping" while `nn_growth_convergence_threshold` is a convergence metric.

---

### RC-10: candidate_learning_rate Unmapped [LOW]

**Severity**: LOW
**Identified by**: Phase 3 v4; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

CasCor has `candidate_learning_rate` in `TrainingParamUpdateRequest` (line 49) and in `updatable_keys` (line 547). Canopy has no mapping for it in `_CANOPY_TO_CASCOR_PARAM_MAP`.

**Impact**: Users cannot adjust candidate learning rate from the Canopy dashboard.

---

### RC-11: Double Initialization on Fallback-to-Demo Path [LOW]

**Severity**: LOW
**Identified by**: Phase 3 v6; 3 of 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

In `main.py`, when CasCor is unreachable:

- Line 177: `await backend.initialize()` — inside the fallback block
- Line 180: `await backend.initialize()` — unconditionally after the if block

The demo backend's `initialize()` is likely idempotent, so this is a code quality issue rather than a functional bug.

---

### RC-12: Dashboard Ignores WebSocket Relay [LOW]

**Severity**: LOW — Architectural; not a bug
**Identified by**: All 7 Phase 3 proposals; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

The dashboard uses HTTP polling at 1-second intervals exclusively. The WebSocket relay broadcasts messages to browser clients, but no dashboard component consumes them. This is adequate for current needs but suboptimal for latency-sensitive displays.

---

### RC-13: Phase 1 Test Coverage Gap [LOW]

**Severity**: LOW
**Identified by**: Phase 3 v5; 3 of 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

All Phase 1 test classes validate flat key production from `_normalize_metric()`. None verify that the output is compatible with the dashboard's nested access patterns. No contract tests compare demo and service output shapes. Zero test files reference `BackendProtocol`.

---

### RC-14: Dual Status Normalization Inconsistency [INFO]

**Severity**: INFO — Architectural observation
**Identified by**: Phase 3 v4; 3 of 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

Two independent normalization paths produce different representations:

- **Path A** (`ServiceBackend.get_status()`): Uses `.upper()` comparison, returns boolean flags (`is_running`, `is_paused`) plus raw `fsm_status`
- **Path B** (relay → `_normalize_status()`): Returns title-case strings (`"Started"`, `"Paused"`)

Not a functional blocker. Both paths produce values the dashboard can consume correctly through their respective consumers.

---

### RC-SYS: No Canonical Backend Contract [SYSTEMIC]

**Severity**: SYSTEMIC — Underlying architectural root cause
**Identified by**: Phase 3 v6, v7; all 4 Phase 4 proposals
**Phase 5 Validation**: ✅ **CONFIRMED**

`BackendProtocol` (`protocol.py:59-140`) returns `Dict[str, Any]` for all methods. No TypedDict, dataclass, or structured return types are used. `data_adapter.py` defines `TrainingMetrics`, `NetworkNode`, `NetworkConnection`, and `NetworkTopology` dataclasses, but `BackendProtocol` does not reference them, and neither backend implementation returns instances of these types. They are dead abstractions.

This is the deepest root cause underlying RC-01, RC-02, RC-05, RC-08, and Phase 1's failure. Without enforced contracts, demo and service modes silently diverge in output format.

---

## 6. Detailed Issue Analysis

---

## 7. Retracted / Rejected Issues

### RETRACTED-1: /api/state Parameter Initialization Uses Hardcoded Defaults

**Originally raised by**: Phase 3 v1, v3
**Retracted by**: v1 and v3 (self-corrected during validation)
**Reason**: Code at `main.py:612-614` already overlays real CasCor values via `get_canopy_params()`. The `setdefault()` calls only provide fallbacks.

### RETRACTED-2: Fallback-to-Demo Path Doesn't Re-Sync training_state

**Originally raised by**: Phase 3 v5
**Retracted by**: v5 (self-corrected during validation)
**Reason**: After fallback, the lifespan function's demo-mode sync block (`main.py:183-202`) correctly syncs `training_state` from the demo backend.

### RETRACTED-3: /api/metrics Current Snapshot as Separate Root Cause

**Originally raised by**: Phase 3 v6; Phase 4 `66a019dc` (as P4-RC-09)
**Status**: Subsumed by RC-01
**Reason**: `get_current_metrics()` calls the same `_normalize_metric()` producing the same flat format. The RC-01 fix must be applied here too, but it is the same bug, not a separate root cause.

### RETRACTED-4: Uppercase Status Normalization Gap

**Originally raised by**: Phase 3 v4, v7; all 4 Phase 4 proposals (as HIGH/MODERATE)
**Status**: **REFUTED by Phase 5 validation**
**Reason**: CasCor WebSocket messages send title-case strings (e.g., `"Started"`, `"Paused"`) via `TrainingState.update_state()` calls in `manager.py:111` and similar. These are already handled by `_normalize_status()`. CasCor never sends uppercase enum `.name` values (e.g., `"STARTED"`) over WebSocket. The REST-based sync path at `state_sync.py:70` does call `.lower()`. The gap is theoretical only.

---

## 8. Cross-Proposal Agreement Matrix

This matrix shows which Phase 3 proposals (as reported by Phase 4) identified each Phase 5 root cause.

| Root Cause                     | v1 | v2 | v3 | v4 | v5 | v6 | v7 | Consensus |
|--------------------------------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|-----------|
| RC-01 (metrics format)         | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7       |
| RC-02 (topology format)        | —  | ✅ | —  | ✅ | —  | —  | —  | 2/7       |
| RC-03 (relay omits fields)     | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7       |
| RC-04 (CasCor phase stuck)     | —  | —  | —  | —  | ✅ | —  | —  | 1/7       |
| RC-05 (state sync raw metrics) | ✅ | —  | ✅ | —  | ✅ | ✅ | ✅ | 5/7       |
| RC-06 (hardcoded URLs)         | —  | —  | —  | ✅ | —  | —  | —  | 1/7       |
| RC-07 (dataset empty)          | —  | —  | —  | ✅ | —  | —  | —  | 1/7       |
| RC-08 (relay raw metrics)      | —  | —  | —  | ✅ | —  | —  | ✅ | 2/7       |
| RC-09 (candidate_epochs dead)  | —  | ✅ | —  | ✅ | —  | —  | —  | 2/7       |
| RC-10 (unmapped candidate_lr)  | —  | —  | —  | ✅ | —  | —  | —  | 1/7       |
| RC-11 (double init)            | —  | —  | —  | —  | —  | ✅ | —  | 1/7       |
| RC-12 (polling only)           | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7       |
| RC-13 (test gap)               | —  | —  | —  | —  | ✅ | —  | —  | 1/7       |
| RC-14 (dual normalization)     | —  | —  | —  | ✅ | —  | —  | —  | 1/7       |
| RC-SYS (no contract)           | —  | —  | —  | —  | —  | ✅ | ✅ | 2/7       |

**Analysis**: 7/7 consensus on RC-01, RC-03, RC-12 (the original Phase 2 findings). 10 issues found by only 1-2 proposals, underscoring the value of the multi-proposal approach. Most comprehensive proposals: v4 (widest scope), v5 (unique cross-repo discovery), v6/v7 (systemic architectural analysis).

---

## 9. Root Cause Dependency Graph

```bash
RC-SYS (SYSTEMIC: No canonical backend contract)
  │
  ├── RC-01 (CRITICAL: Metrics flat vs nested mismatch) ──── PRIMARY BLOCKER
  │     │
  │     ├── RC-05 (MODERATE: State sync raw metrics — latent, no consumer)
  │     └── RC-08 (LOW: Relay broadcasts raw metrics — latent)
  │
  ├── RC-02 (CRITICAL: Topology format mismatch) ──── SECONDARY BLOCKER
  │
  ├── RC-03 (MODERATE: Relay callback omits fields)
  │
  └── RC-12 (LOW: Dashboard ignores relay)

RC-04 (MODERATE: CasCor phase stuck) ──── Independent, cross-repo

RC-06 (MODERATE: Hardcoded URLs) ──── Independent
RC-07 (MODERATE: Dataset empty) ──── Independent, CasCor API limitation
RC-09 (LOW: Dead param mapping) ──── Independent
RC-10 (LOW: Unmapped candidate_lr) ──── Independent
RC-11 (LOW: Double init) ──── Independent
RC-13 (LOW: Test coverage gap) ──── Independent
RC-14 (INFO: Dual normalization) ──── Independent
```

---

## 10. Verified Working Subsystems

These data paths function correctly and require no changes:

| Subsystem                                         | Mechanism                                                                            | Verified |
|---------------------------------------------------|--------------------------------------------------------------------------------------|----------|
| Status bar (is_running, phase, epoch)             | `ServiceBackend.get_status()` → fresh REST calls → flat keys → status bar reads flat | ✅       |
| Decision boundary visualization                   | `get_decision_boundary()` transforms `grid_x`/`grid_y` → `xx`/`yy`/`Z` correctly     | ✅       |
| Dataset metadata display                          | `ServiceBackend.get_dataset()` maps `train_samples` → `num_samples` correctly        | ✅       |
| Training controls (start/stop/pause/resume/reset) | REST forwarding with proper error handling                                           | ✅       |
| Parameter updates (apply_params)                  | `_CANOPY_TO_CASCOR_PARAM_MAP` correctly maps canopy → CasCor names                   | ✅       |
| WebSocket relay connection                        | Relay establishes WebSocket and receives messages                                    | ✅       |
| Non-destructive attach                            | CasCor attach endpoint correctly handles non-destructive mode                        | ✅       |
| ResponseEnvelope unwrapping                       | All 14 Phase 1 fixes correctly implemented                                           | ✅       |

---

## 11. Fix Recommendations

### FIX-A: Metrics Format Transformation (addresses RC-01)

**Priority**: P0 — CRITICAL
**Effort**: Small (1-2 hours)
**All proposals unanimously recommend this approach.**

Add `_to_dashboard_metric()` transformation after `_normalize_metric()`:

```python
@staticmethod
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format.

    Matches the format produced by DemoMode._emit_training_metrics().
    The dashboard (metrics_panel.py) reads metrics using nested access:
      m.get("metrics", {}).get("loss", 0)
      m.get("network_topology", {}).get("hidden_units", 0)
    """
    return {
        "epoch": flat.get("epoch", 0),
        "metrics": {
            "loss": flat.get("train_loss"),
            "accuracy": flat.get("train_accuracy"),
            "val_loss": flat.get("val_loss"),
            "val_accuracy": flat.get("val_accuracy"),
        },
        "network_topology": {
            "hidden_units": flat.get("hidden_units", 0),
        },
        "phase": flat.get("phase"),
        "timestamp": flat.get("timestamp"),
    }
```

Apply in:

- `_ServiceTrainingMonitor.get_recent_metrics()` — wrap each entry after `_normalize_metric()`
- `_ServiceTrainingMonitor.get_current_metrics()` — wrap result after `_normalize_metric()`

**Advantages**: Single transformation point, no dashboard changes, preserves Phase 1 normalization boundary, testable independently, demo path untouched.

**Risks**: LOW — `network_topology` will only contain `hidden_units` (missing `input_units`, `output_units` that demo mode includes), but dashboard only reads `hidden_units` from this sub-dict.

---

### FIX-B: Topology Format Transformation (addresses RC-02)

**Priority**: P0 — CRITICAL
**Effort**: Medium (2-3 hours)

Add `_transform_topology()` in `cascor_service_adapter.py` to convert CasCor's weight-oriented topology to the graph-oriented format the visualizer expects:

```python
@staticmethod
def _transform_topology(raw: dict) -> dict:
    """Transform CasCor weight-oriented topology to graph-oriented format.

    CasCor returns: {input_size, output_size, hidden_units: [{weights, bias, activation}]}
    Dashboard expects: {input_units, output_units, hidden_units (int), nodes: [...], connections: [...]}
    """
    input_count = raw.get("input_size", 0)
    output_count = raw.get("output_size", 0)
    hidden_list = raw.get("hidden_units", [])

    nodes = []
    connections = []

    # Build input nodes
    for i in range(input_count):
        nodes.append({"id": f"i{i}", "type": "input", "label": f"Input {i}"})

    # Build hidden nodes and connections from weights
    for h_idx, hu in enumerate(hidden_list):
        h_id = f"h{h_idx}"
        nodes.append({"id": h_id, "type": "hidden", "label": f"Hidden {h_idx}"})
        weights = hu.get("weights", [])
        # Input-to-hidden connections
        for w_idx, w in enumerate(weights[:input_count]):
            connections.append({"from": f"i{w_idx}", "to": h_id, "weight": w})
        # Hidden-to-hidden connections (from prior hidden units)
        for prev_idx, w in enumerate(weights[input_count:]):
            if prev_idx < h_idx:
                connections.append({"from": f"h{prev_idx}", "to": h_id, "weight": w})

    # Build output nodes and connections
    output_weights = raw.get("output_weights", [])
    for o_idx in range(output_count):
        o_id = f"o{o_idx}"
        nodes.append({"id": o_id, "type": "output", "label": f"Output {o_idx}"})
        if o_idx < len(output_weights):
            o_w = output_weights[o_idx]
            # Input-to-output
            for w_idx in range(min(input_count, len(o_w))):
                connections.append({"from": f"i{w_idx}", "to": o_id, "weight": o_w[w_idx]})
            # Hidden-to-output
            for h_idx in range(len(hidden_list)):
                w_offset = input_count + h_idx
                if w_offset < len(o_w):
                    connections.append({"from": f"h{h_idx}", "to": o_id, "weight": o_w[w_offset]})

    return {
        "input_units": input_count,
        "output_units": output_count,
        "hidden_units": len(hidden_list),
        "nodes": nodes,
        "connections": connections,
    }
```

Apply in `extract_network_topology()` after `_unwrap_response()`.

**Risks**: MEDIUM — Weight array indexing assumptions need verification against CasCor's actual cascade correlation architecture. Integration test with real CasCor response recommended.

---

### FIX-C: Expand Relay State Callback (addresses RC-03)

**Priority**: P1 — MODERATE
**Effort**: Small (30 minutes)

Expand the relay callback invocation:

```python
self._state_update_callback(
    status=status,
    phase=data.get("phase", ""),
    current_epoch=data.get("current_epoch"),
    current_step=data.get("current_step"),
    learning_rate=data.get("learning_rate"),
    max_hidden_units=data.get("max_hidden_units"),
    max_epochs=data.get("max_epochs"),
)
```

`training_state.update_state()` accepts `**kwargs` and ignores `None` values, so this is safe.

---

### FIX-D: CasCor Monitor Phase Update (addresses RC-04)

**Priority**: P1 — MODERATE (cross-repo)
**Effort**: Small (1 hour)

In `juniper-cascor/src/api/lifecycle/monitor.py`, add a `set_phase()` method. In `manager.py`, call `monitor.set_phase()` on each phase transition (output → candidate → output).

Can be shipped independently — canopy fixes work without this but will show incorrect phase labels.

---

### FIX-E: Normalize State Sync Metrics (addresses RC-05)

**Priority**: P2 — LOW (no current consumer)
**Effort**: Small (30 minutes)

Apply `_normalize_metric()` + `_to_dashboard_metric()` to each entry in `state_sync.py:121-127` before storing in `state.metrics_history`. Only becomes necessary if synced metrics history gains a downstream consumer.

---

### FIX-F: Replace Hardcoded URLs (addresses RC-06)

**Priority**: P2 — MODERATE
**Effort**: Trivial (15 minutes)

Replace 6 hardcoded `localhost:8050` URLs in `metrics_panel.py` with relative paths or a dynamic base URL.

---

### FIX-G: Fix Parameter Mappings (addresses RC-09, RC-10)

**Priority**: P3 — LOW
**Effort**: Small (30 minutes)

- Remove or update `cn_training_iterations` → `candidate_epochs` mapping (not runtime-updatable)
- Add `candidate_learning_rate` mapping to `_CANOPY_TO_CASCOR_PARAM_MAP`
- Review `patience` → `nn_growth_convergence_threshold` semantic alignment

---

### FIX-H: Guard Double Initialization (addresses RC-11)

**Priority**: P3 — LOW
**Effort**: Trivial (15 minutes)

Add `else` clause or `initialized` flag in `main.py` fallback path to prevent double `backend.initialize()`.

---

### FIX-I: Contract Tests (addresses RC-13, RC-SYS)

**Priority**: P2 — MODERATE (preventive)
**Effort**: Medium (2-3 hours)

Add tests comparing demo and service backend output shapes. Update existing `test_response_normalization.py` to verify nested output format.

---

## 12. Implementation Priority and Ordering

### Phase A: Critical Display Blockers (P0)

| Priority | Fix   | Issue(s) | Effort | Risk   |
|----------|-------|----------|--------|--------|
| 1        | FIX-A | RC-01    | Small  | Low    |
| 2        | FIX-B | RC-02    | Medium | Medium |

**After Phase A**: Metrics charts display live data, topology renders — core dashboard functionality restored.

FIX-A and FIX-B can be implemented in parallel. FIX-A alone will restore metrics charts.

### Phase B: Active Bugs and Quality (P1-P2)

| Priority | Fix   | Issue(s)      | Effort  | Risk |
|----------|-------|---------------|---------|------|
| 3        | FIX-C | RC-03         | Small   | Low  |
| 4        | FIX-D | RC-04         | Small   | Low  |
| 5        | FIX-F | RC-06         | Trivial | None |
| 6        | FIX-I | RC-13, RC-SYS | Medium  | None |
| 7        | FIX-E | RC-05         | Small   | Low  |

### Phase C: Low Priority and Polish (P3+)

| Priority | Fix   | Issue(s)                      | Effort  | Risk   |
|----------|-------|-------------------------------|---------|--------|
| 8        | FIX-G | RC-09, RC-10                  | Small   | Low    |
| 9        | FIX-H | RC-11                         | Trivial | None   |
| 10       | —     | RC-07 (dataset)               | Large   | Medium |
| 11       | —     | RC-08 (relay normalize)       | Small   | Low    |
| 12       | —     | RC-12 (WebSocket consumption) | Large   | Medium |

### Dependency Graph

```bash
FIX-A (RC-01) ──────┬── FIX-E (RC-05, depends on _to_dashboard_metric)
                     │
FIX-B (RC-02) ──────┤── FIX-I (RC-13, tests against fixed output)
                     │
FIX-C (RC-03) ──────┘   (parallel)
FIX-D (RC-04) ──────     (independent, cross-repo)
FIX-F (RC-06) ──────     (independent)
FIX-G (RC-09/10) ──      (independent)
FIX-H (RC-11) ──────     (independent)
```

---

## 13. Risk Assessment

| Risk                                                    | Likelihood | Impact | Mitigation                                                           |
|---------------------------------------------------------|------------|--------|----------------------------------------------------------------------|
| `_to_dashboard_metric()` breaks demo mode               | Low        | High   | Only applied in service path; demo path untouched                    |
| Topology weight ordering assumption incorrect           | Medium     | Medium | Test against actual CasCor responses; validate connection counts     |
| FakeCascorClient divergence masks new issues            | High       | Medium | Add contract tests; FakeCascorClient uses a third format             |
| Multiple simultaneous fixes introduce regressions       | Medium     | Medium | Fix and test one issue at a time; run full suite between             |
| Falsy values (epoch=0, loss=0.0) treated as missing     | Medium     | Medium | Use `_first_defined()` helper (already exists); `is not None` checks |
| Phase 1 test assertions need updating for nested format | High       | Low    | Expected; update assertions as part of FIX-A                         |
| CasCor cross-repo fix (RC-04) requires coordination     | Medium     | Low    | Canopy fixes are independent; phase labels degrade gracefully        |
| Demo mode regresses from shared code changes            | Low        | High   | Normalization code is separate; add regression test                  |

---

## 14. Verification Plan

### 14.1 Automated Tests

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython

# Unit tests
pytest tests/unit/ -v

# Integration tests (mock-based)
pytest tests/integration/ -v -m "not requires_cascor"

# Regression tests
pytest tests/regression/ -v

# Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### 14.2 New Contract Tests (FIX-I)

```python
def test_metrics_history_contract_matches_demo():
    """Service and demo backends return same metric entry structure."""
    service_entry = service_backend.get_metrics_history(1)[0]
    demo_entry = demo_backend.get_metrics_history(1)[0]
    assert set(service_entry.keys()) == set(demo_entry.keys())
    assert "metrics" in service_entry  # nested, not flat
    assert "network_topology" in service_entry

def test_topology_contract_matches_demo():
    """Service and demo backends return same topology structure."""
    service_topo = service_backend.get_network_topology()
    demo_topo = demo_backend.get_network_topology()
    assert "input_units" in service_topo
    assert "connections" in service_topo
    assert set(service_topo.keys()) == set(demo_topo.keys())
```

### 14.3 Manual Integration Test

```bash
# Terminal 1: Start juniper-data
cd /home/pcalnon/Development/python/Juniper/juniper-data
conda activate JuniperData
PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100

# Terminal 2: Start juniper-cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
JUNIPER_CASCOR_PORT=8201 python server.py

# Terminal 3: Start juniper-canopy (service mode)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 4: Verify API responses
# Metrics (RC-01 — should now be nested):
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, "phase": "...", ...}]}

# Topology (RC-02 — should now be graph-oriented):
curl -s http://localhost:8050/api/network/topology | python3 -m json.tool
# Expected: {"input_units": 2, "output_units": 1, "hidden_units": N,
#            "nodes": [...], "connections": [...]}

# Status (should already work):
curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 14.4 Visual Verification Checklist

- [ ] Loss chart displays live training data (not flat line at 0)
- [ ] Accuracy chart displays accuracy curve (not flat at 0)
- [ ] Current loss display shows actual value (not "0.0000" or "--")
- [ ] Current accuracy display shows actual percentage (not "0.00%")
- [ ] Hidden units count shows actual count (not always 0)
- [ ] Hidden unit addition markers appear on plots at cascade events
- [ ] Network graph shows input/hidden/output nodes with connections
- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Phase indicator shows Output/Candidate transitions
- [ ] Parameter panel shows actual CasCor parameters
- [ ] Stopping canopy does not stop CasCor training
- [ ] Restarting canopy reconnects and shows correct state/metrics
- [ ] Connect to CasCor with training already in progress (non-destructive attach)

---

## 15. Files Requiring Modification

### juniper-canopy

| File                                            | Root Causes                              | Changes                                                                                                                                                                                      |
|-------------------------------------------------|------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `src/backend/cascor_service_adapter.py`         | RC-01, RC-02, RC-03, RC-08, RC-09, RC-10 | Add `_to_dashboard_metric()`, apply in `get_recent_metrics()`, `get_current_metrics()`; add `_transform_topology()`, apply in `extract_network_topology()`; expand relay c/b; fix param maps |
| `src/backend/state_sync.py`                     | RC-05                                    | Normalize synced metrics history (low priority)                                                                                                                                              |
| `src/frontend/components/metrics_panel.py`      | RC-06                                    | Replace 6 hardcoded `localhost:8050` URLs                                                                                                                                                    |
| `src/main.py`                                   | RC-11                                    | Guard double initialization on fallback path                                                                                                                                                 |
| `src/tests/unit/test_response_normalization.py` | RC-13                                    | Add nested format contract tests; update flat-format assertions                                                                                                                              |

### juniper-cascor (cross-repo)

| File                           | Root Causes | Changes                                          |
|--------------------------------|-------------|--------------------------------------------------|
| `src/api/lifecycle/monitor.py` | RC-04       | Add `set_phase()` method; update `current_phase` |
| `src/api/lifecycle/manager.py` | RC-04       | Call `monitor.set_phase()` on phase transitions  |

### Files NOT Requiring Modification

- `metrics_panel.py` (for RC-01) — fix is in backend, not the panel
- `dashboard_manager.py` — callbacks are correct; data they receive is wrong
- `demo_mode.py` — demo format is the target format (working reference)
- `network_visualizer.py` (for RC-02) — fix is in adapter, not the visualizer
- `juniper-cascor-client/` — no changes needed (Phase 1 FIX-SYS already done)

---

## 16. Post-Synthesis Validation Results

All claims in this document were validated against the source code using 5 specialized verification sub-agents. This section documents outcomes and corrections applied.

### Validation Summary

| Root Cause           | Validation Result                                                           | Corrections from Phase 4                                        |
|----------------------|-----------------------------------------------------------------------------|-----------------------------------------------------------------|
| RC-01                | **CONFIRMED** — all 10 line numbers exact; full data path traced            | None needed                                                     |
| RC-02                | **CONFIRMED** — all 6 structural mismatches verified; passthrough confirmed | Added: FakeCascorClient uses a third format                     |
| RC-03                | **CONFIRMED** — relay callback passes only `status` + `phase`               | Clarified: broadcast to browsers includes full message          |
| RC-04                | **CONFIRMED** — `current_phase` assigned once at init, zero other writes    | None needed                                                     |
| RC-05                | **CONFIRMED** — low practical impact                                        | Added: `metrics_history` has no downstream consumer currently   |
| RC-06                | **CONFIRMED** — 6 hardcoded URLs (corrected from 2 in some proposals)       | Count corrected; exact line numbers provided                    |
| RC-07                | **CONFIRMED** — metadata only, no data arrays                               | None needed                                                     |
| RC-08                | **CONFIRMED** — raw CasCor payloads broadcast with zero normalization       | None needed                                                     |
| RC-09                | **CONFIRMED** — reclassified from "dead code"                               | `candidate_epochs` exists on config but not in `updatable_keys` |
| RC-10                | **CONFIRMED** — in `TrainingParamUpdateRequest` and `updatable_keys`        | None needed                                                     |
| RC-11                | **CONFIRMED** — lines 177 and 180 both call `initialize()`                  | None needed                                                     |
| RC-12                | **CONFIRMED** — zero WebSocket callback bindings                            | None needed                                                     |
| RC-13                | **CONFIRMED** — all tests validate flat keys only                           | None needed                                                     |
| RC-14                | **CONFIRMED** — two paths, different representations                        | None needed                                                     |
| RC-SYS               | **CONFIRMED** — `Dict[str, Any]` everywhere; dead dataclass abstractions    | Added: `data_adapter.py` has unused TypedDict/dataclass types   |
| ~~Uppercase status~~ | **REFUTED** — CasCor sends title-case, already handled                      | **Removed from active issues**                                  |

### Key Phase 5 Validation Insights

1. **Uppercase status retraction**: This was raised by Phase 3 v4 and v7 and carried forward by all 4 Phase 4 proposals. Phase 5 validation definitively showed CasCor sends title-case strings over WebSocket, which `_normalize_status()` already handles. This is the most significant correction from Phase 5.

2. **State sync metrics (RC-05) impact reduction**: All 4 Phase 4 proposals rated this MODERATE. Phase 5 found the stored `metrics_history` has no active consumer, reducing practical impact to near-zero.

3. **RC-09 reclassification**: Phase 4 proposals called this "dead code." Phase 5 found the mapping executes successfully — CasCor has `candidate_epochs` on the config — but the PATCH endpoint doesn't accept it. It's not dead code; it's a non-functional mapping.

4. **FakeCascorClient format divergence**: Phase 5 discovered the fake client in `scenarios.py` returns a third topology format (graph-oriented but with `input_size`/`output_size`), distinct from both real CasCor and demo mode. This compounds the contract enforcement problem (RC-SYS).

---

## Appendix A: Phase 4 Proposal Assessment

### Agreement and Divergence

| Aspect               | `002192f3`            | `66a019dc`                | `cd8254d3`                                | `d7dcbd5a`                    |
|----------------------|-----------------------|---------------------------|-------------------------------------------|-------------------------------|
| Total issues         | 13                    | 16                        | 15 + 1 KL                                 | 19                            |
| Critical blockers    | 2 (correct)           | 2 (correct)               | 1 CRITICAL + 1 MODERATE topo (underrated) | 2 (correct)                   |
| Uppercase status     | HIGH                  | HIGH                      | MODERATE (latent) — most accurate         | HIGH (latent)                 |
| Hardcoded URL count  | 6                     | 6                         | Initially 2, corrected to 6               | 6                             |
| Unique contributions | Clean priority matrix | Dependency chain analysis | Known-limitation designation (KL-1)       | Deepest architecture analysis |

### Per-Proposal Evaluation

| UUID       | Accuracy | Completeness | Rigor                          | Best At                                                |
|------------|----------|--------------|--------------------------------|--------------------------------------------------------|
| `002192f3` | High     | Good         | Strong — explicit retractions  | Clear, actionable fix ordering                         |
| `66a019dc` | High     | Highest      | Strong — dependency chain      | Most comprehensive; best implementation plan           |
| `cd8254d3` | Highest  | Good         | Strongest — 3 self-corrections | Best self-validation; most intellectually honest       |
| `d7dcbd5a` | High     | Highest      | Strong — appendices            | Deepest architectural insight; best evidence inventory |

**Most accurate on uppercase status**: `cd8254d3` — rated it as "CONFIRMED as LATENT" and noted CasCor currently broadcasts title-case, not uppercase. This was the closest to Phase 5's full refutation.

---

## Appendix B: Document Lineage

```bash
Phase 0 (Original Analysis):
  1_CANOPY_EXTERNAL_CASCOR_PLAN.md
  2_INVESTIGATION_PLAN_EXTERNAL_CASCOR_METRICS_DISPLAY.md
  3_ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md
  4_CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md

Phase 1 (Development Plans — Implemented):
  5a_EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md
  5b_DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md

Phase 2 (Root Cause Analysis — Implemented):
  PHASE_2_MERGED_EXTERNAL_CASCOR_DEV_PLAN_v1.md
  PHASE_2_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY_v3.md
  PHASE_2_UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN_v2.md

Phase 3 (Independent Proposals — 7 documents):
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v1.md through v7.md

Phase 4 (Synthesis — 4 documents):
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_002192f3-fbde-444b-ac3f-2c0e6ceb8f96.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_66a019dc-94ba-47fb-8042-7ce8f974d071.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_cd8254d3-16bb-4212-b551-d9e911afd690.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_d7dcbd5a-667d-48ba-8d3a-f11893105c6a.md

Phase 5 (This Document — Final Synthesis):
  PHASE_5_CANOPY_CASCOR_CONNECTION_ANALYSIS_7f73219c-1557-4135-ab44-ef053d4c4097.md
```
