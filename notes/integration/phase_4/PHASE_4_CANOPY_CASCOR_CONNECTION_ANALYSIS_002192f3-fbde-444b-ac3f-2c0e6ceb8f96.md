# Phase 4 Comprehensive Analysis: External CasCor Display Failure

**Version**: 1.0.0
**Date**: 2026-03-27
**UUID**: 002192f3-fbde-444b-ac3f-2c0e6ceb8f96
**Author**: Amp (AI Agent)
**Status**: Analysis Complete — Validated
**Predecessors**:

- `CANOPY_EXTERNAL_CASCOR_PLAN.md` (Original gap analysis)
- `CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md` (Data flow investigation)
- `MERGED_EXTERNAL_CASCOR_DEV_PLAN.md` (Phase 1 — implemented)
- `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` (Phase 1 — implemented)
- `ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md` (Phase 2 — analysis)
- 7 independent Phase 3 proposals in `notes/integration/proposals/`

---

## 1. Executive Summary

This Phase 4 analysis synthesizes, cross-references, and validates findings from 7 independent Phase 3 root cause proposals, each of which independently evaluated the Phase 1 and Phase 2 debugging documents and the current Juniper project codebase. All findings have been verified against the actual source code across juniper-canopy, juniper-cascor, and juniper-cascor-client.

### Methodology

1. All 7 Phase 3 proposals were read and cataloged
2. Root causes were deduplicated and cross-referenced across proposals
3. Each unique issue was synthesized from all proposals that identified it
4. All claims were validated against the current codebase using targeted code inspection
5. False positives were identified and documented
6. Findings were corrected where validation contradicted proposal claims

### Results

| Category | Count |
|----------|-------|
| Total unique issues identified | 15 |
| Retracted as false positives | 2 |
| **Active verified issues** | **13** |
| Display blockers | 2 |
| Proposals analyzed | 7 |

### Critical Findings

| Priority | Issue | Severity | Display Blocker | Proposals |
|----------|-------|----------|-----------------|-----------|
| 1 | ISSUE-1: Metrics data format mismatch (flat vs nested) | **CRITICAL** | **Yes** | All 7 |
| 2 | ISSUE-4: Topology data format mismatch (weight vs graph) | **CRITICAL** | **Yes** | v2, v4 |
| 3 | ISSUE-5: Uppercase status normalization gap in relay path | HIGH | No | v4, v7 |
| 4 | ISSUE-10: CasCor TrainingMonitor never updates current_phase | MODERATE | No | v5 |

**Bottom line**: Fixing ISSUE-1 alone will restore metrics charts. Fixing ISSUE-4 will restore topology visualization. These are the only two display blockers. All other issues affect data freshness, correctness, or architectural quality but do not prevent the dashboard from displaying data.

---

## 2. Methodology

### 2.1 Phase 3 Proposal Inventory

| Proposal | Author | Key Unique Findings | Total RCs |
|----------|--------|---------------------|-----------|
| v1 | Claude (Opus 4.6) | RC-4 false positive identified, RC-5 latent sync bug | 5 (1 retracted) |
| v2 | Claude (Opus 4.6) | **Topology format mismatch** (unique), parameter mapping issues | 6 |
| v3 | Claude (Opus 4.6) | Identical findings to v1, confirmed false positive | 5 (1 retracted) |
| v4 | Claude (Opus 4.6) | **Hardcoded URLs** (unique), uppercase status gap, 11 total RCs | 11 |
| v5 | Claude (Opus 4.6) | **CasCor monitor phase bug** (unique, cross-repo), test gap | 7 (1 retracted) |
| v6 | Amp | Double initialization, systemic contract gap, /api/metrics path | 7 |
| v7 | Amp | Uppercase status gap, relay normalization, systemic contract gap | 7 |

### 2.2 Validation Approach

Each issue was validated by:

1. Reading the exact source file and line numbers cited
2. Tracing complete data paths from producer to consumer
3. Comparing actual code behavior against proposal claims
4. Cross-referencing contradictory claims between proposals

### 2.3 Repositories Examined

| Repository | Key Files | Purpose |
|------------|-----------|---------|
| juniper-canopy | `cascor_service_adapter.py`, `service_backend.py`, `state_sync.py`, `main.py`, `metrics_panel.py`, `network_visualizer.py`, `dashboard_manager.py`, `demo_mode.py` | Backend normalization, frontend consumption |
| juniper-cascor | `api/lifecycle/manager.py`, `api/lifecycle/monitor.py`, `api/lifecycle/state_machine.py`, `api/routes/metrics.py`, `api/models/common.py` | Server API response formats |
| juniper-cascor-client | `client.py`, `ws_client.py`, `testing/fake_client.py` | Client library behavior |

---

## 3. Validated Issue Catalog

### ISSUE-1: Metrics Data Format Mismatch (Flat Keys vs Nested Keys)

**Severity**: CRITICAL
**Identified By**: All 7 proposals (v1, v2, v3, v4, v5, v6, v7)
**Category**: Metrics
**Display Blocker**: Yes
**Validation**: ✅ CONFIRMED

#### Description

The service backend's `_normalize_metric()` method (`cascor_service_adapter.py:431-460`) produces metrics with **flat** top-level keys (`train_loss`, `train_accuracy`, `hidden_units`), but the dashboard's `MetricsPanel` component (`metrics_panel.py`) reads metrics using **nested** dictionary access patterns (`metrics.loss`, `metrics.accuracy`, `network_topology.hidden_units`).

This mismatch exists because Phase 1 defined a "Canonical Internal Contract" (Section 6.2) with flat keys by analyzing what cascor sends and what canopy should normalize to, but **never validated this contract against the dashboard's actual input format**. The dashboard was built against demo mode, which produces a nested format. The status bar works because it reads flat keys from `/api/status` — not the metrics store.

#### Complete Data Flow (Service Mode — Broken)

```text
cascor TrainingMonitor.on_epoch_end()
  → {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase}
  → wrapped in ResponseEnvelope

JuniperCascorClient.get_metrics_history()
  → returns raw response.json() (full ResponseEnvelope)

_ServiceTrainingMonitor.get_recent_metrics()
  → unwraps envelope → normalizes each entry via _normalize_metric()
  → FLAT: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units, phase}

ServiceBackend.get_metrics_history() → passes through FLAT list
main.py /api/metrics/history → {"history": [FLAT]}
dashboard_manager → stores FLAT list in metrics-panel-metrics-store

MetricsPanel reads:
  metric.get("metrics", {}).get("loss", 0)              → ALWAYS 0
  metric.get("network_topology", {}).get("hidden_units", 0) → ALWAYS 0
```

#### Dashboard Access Patterns (9 Locations)

| Line | Code | Expected Path | Flat Key | Result |
|------|------|---------------|----------|--------|
| 1091 | `m.get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units` | **0** |
| 1120 | `latest.get("metrics", {}).get("loss", 0)` | `metrics.loss` | `train_loss` | **0** |
| 1121 | `latest.get("metrics", {}).get("accuracy", 0)` | `metrics.accuracy` | `train_accuracy` | **0** |
| 1122 | `latest.get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units` | **0** |
| 1330 | `metric.get("metrics", {}).get("loss", 0)` | `metrics.loss` | `train_loss` | **0** |
| 1449-1450 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units` | **0** |
| 1499 | `metric.get("metrics", {}).get("accuracy", 0)` | `metrics.accuracy` | `train_accuracy` | **0** |
| 1561-1562 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units` | **0** |

#### Field Name Mapping (Non-Trivial)

| Flat Key (from `_normalize_metric`) | Required Nested Path (dashboard) |
|-------------------------------------|----------------------------------|
| `train_loss` | `metrics.loss` (prefix stripped) |
| `train_accuracy` | `metrics.accuracy` (prefix stripped) |
| `val_loss` | `metrics.val_loss` |
| `val_accuracy` | `metrics.val_accuracy` |
| `hidden_units` | `network_topology.hidden_units` |

#### Impact

- **Loss chart**: All y-values read as 0 → flat line or empty
- **Accuracy chart**: All y-values read as 0 → flat line or empty
- **Current loss/accuracy indicators**: Show "0.0000" or "--"
- **Hidden unit count**: Always 0
- **Hidden unit addition markers**: Never rendered

#### Recommended Fix

All 7 proposals converge on the same approach: add a `_to_dashboard_metric()` transformation after `_normalize_metric()`:

```python
@staticmethod
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format.

    Matches the format produced by DemoMode._emit_training_metrics().
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

Apply in `_ServiceTrainingMonitor.get_recent_metrics()` and `get_current_metrics()`.

**Advantages**: Single transformation point, no dashboard changes, preserves Phase 1 normalization boundary, testable independently.

**Risks**: LOW — `network_topology` will only contain `hidden_units` (missing `input_units`, `output_units` that demo mode includes), but the dashboard only reads `hidden_units` from this sub-dict.

---

### ISSUE-2: WebSocket Relay State Callback Omits Fields

**Severity**: MODERATE
**Identified By**: All 7 proposals (v1, v2, v3, v4, v5, v6, v7)
**Category**: WebSocket / State Management
**Display Blocker**: No
**Validation**: ✅ CONFIRMED (with correction)

#### Description

The state update callback in the relay loop (`cascor_service_adapter.py:218-225`) only forwards `status` and `phase` to `training_state.update_state()`:

```python
self._state_update_callback(status=status, phase=data.get("phase", ""))
```

CasCor WebSocket `state` messages include `current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, `max_epochs`, `network_name`, `timestamp` — all of which are discarded by the local state callback.

#### Validation Correction

All 7 proposals described this issue, but the validation revealed an important distinction:

- The **WebSocket broadcast** to browser clients (`cascor_service_adapter.py:203-206`) forwards the **full message** including all fields — it does NOT strip fields
- The **local state callback** (`cascor_service_adapter.py:222-223`) only passes `status` and `phase` to `training_state.update_state()`
- The impact is therefore limited to the `training_state` global becoming stale for `current_epoch`, `hidden_units`, etc. between REST polls
- The **status bar is NOT affected** because it reads from `/api/status` which makes a fresh REST call each poll cycle

#### Impact

- `/api/state` endpoint returns stale `current_epoch` after initial sync
- Any component reading from `training_state.get_state()` directly gets stale data
- Status bar and metrics charts are NOT affected (they use independent data paths)

#### Recommended Fix

Expand the callback invocation:

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

`TrainingState.update_state()` accepts `**kwargs` and silently ignores `None` values, so this is safe.

---

### ISSUE-3: Dashboard Uses HTTP Polling, Ignores WebSocket Relay

**Severity**: LOW
**Identified By**: All 7 proposals (v1, v2, v3, v4, v5, v6, v7)
**Category**: Architecture
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

The dashboard uses `dcc.Interval` callbacks for all data fetching:

- `fast-update-interval` (1000ms): status bar, metrics store
- `slow-update-interval` (5000ms): topology, dataset, decision boundary

A `websocket-data` div exists in the layout (`dashboard_manager.py:876`) but no Dash callback reads from it. HTTP polling at 1s intervals is adequate for training progress display.

#### Impact

Latency/efficiency only. Not a functional blocker.

#### Recommended Fix

Future enhancement — add Dash clientside callbacks to consume WebSocket messages. Not required for the feature to work.

---

### ISSUE-4: Topology Data Format Mismatch (Weight-Oriented vs Graph-Oriented)

**Severity**: CRITICAL
**Identified By**: Proposals v2, v4
**Category**: Topology
**Display Blocker**: Yes
**Validation**: ✅ CONFIRMED

#### Description

CasCor's `get_topology()` endpoint (`lifecycle/manager.py:563-588`) returns a **weight-oriented** topology:

```python
{
    "input_size": 2,                     # NOT "input_units"
    "output_size": 1,                    # NOT "output_units"
    "hidden_units": [                    # LIST OF OBJECTS, not an integer
        {"id": 0, "weights": [...], "bias": 0.1, "activation": "sigmoid"},
    ],
    "output_weights": [[...]],
    "output_bias": [...]
}
```

The canopy `NetworkVisualizer` expects a **graph-oriented** format:

```python
{
    "input_units": 2,                    # Integer count
    "output_units": 1,                   # Integer count
    "hidden_units": 3,                   # Integer count (NOT array)
    "nodes": [...],                      # Graph nodes
    "connections": [                     # Graph edges
        {"from": "input_0", "to": "hidden_0", "weight": 0.5},
    ]
}
```

This has two sub-components:

1. **Key name mismatch** (v4 RC-5): `input_size`/`output_size` vs `input_units`/`output_units`
2. **Structure mismatch** (v2 RC-4): Raw weight tensors vs pre-computed graph nodes/connections

The adapter's `extract_network_topology()` (`cascor_service_adapter.py:480-484`) simply unwraps the API response without any transformation. The visualizer checks `topology_data.get("input_units", 0) == 0` for empty-graph detection, which always returns 0 since the key is `input_size`, causing the topology to appear empty.

#### Impact

- Network topology visualization always shows empty graph
- No nodes or connections rendered in service mode
- Demo mode works correctly because `DemoBackend` produces graph-oriented format

#### Recommended Fix (from v2)

Add `_transform_topology()` to `CascorServiceAdapter`:

```python
@staticmethod
def _transform_topology(cascor_topo: dict) -> dict:
    """Transform cascor weight-oriented topology to graph format."""
    input_size = cascor_topo.get("input_size", 0)
    output_size = cascor_topo.get("output_size", 0)
    hidden_units = cascor_topo.get("hidden_units", [])
    hidden_count = len(hidden_units) if isinstance(hidden_units, list) else 0

    nodes = []
    connections = []

    for i in range(input_size):
        nodes.append({"id": f"input_{i}", "type": "input", "layer": 0})

    for i, unit in enumerate(hidden_units if isinstance(hidden_units, list) else []):
        nodes.append({"id": f"hidden_{i}", "type": "hidden", "layer": 1})
        weights = unit.get("weights", [])
        for j, w in enumerate(weights[:input_size]):
            connections.append({"from": f"input_{j}", "to": f"hidden_{i}", "weight": float(w)})
        for j, w in enumerate(weights[input_size:]):
            if j < i:
                connections.append({"from": f"hidden_{j}", "to": f"hidden_{i}", "weight": float(w)})

    output_weights = cascor_topo.get("output_weights", [])
    for i in range(output_size):
        nodes.append({"id": f"output_{i}", "type": "output", "layer": 2})
        if i < len(output_weights):
            row = output_weights[i]
            for j in range(min(input_size, len(row))):
                connections.append({"from": f"input_{j}", "to": f"output_{i}", "weight": float(row[j])})
            for j in range(hidden_count):
                idx = input_size + j
                if idx < len(row):
                    connections.append({"from": f"hidden_{j}", "to": f"output_{i}", "weight": float(row[idx])})

    return {
        "input_units": input_size,
        "output_units": output_size,
        "hidden_units": hidden_count,
        "nodes": nodes,
        "connections": connections,
    }
```

Apply in `extract_network_topology()` with format detection:

```python
def extract_network_topology(self):
    raw = self._unwrap_response(self._client.get_topology())
    if isinstance(raw, dict) and "input_units" in raw:
        return raw  # Already in graph format
    return self._transform_topology(raw)
```

**Risks**: MEDIUM — Weight ordering assumption must match cascor's actual serialization. Cascade correlation networks have cascaded connections (each hidden unit connects to all inputs AND all prior hidden units).

---

### ISSUE-5: Uppercase Status Normalization Gap in WebSocket Relay Path

**Severity**: HIGH
**Identified By**: Proposals v4, v7
**Category**: Status
**Display Blocker**: No
**Validation**: ✅ PARTIALLY CONFIRMED

#### Description

CasCor's `TrainingStateMachine.get_state_summary()` returns status as Python enum `.name` values, which are **UPPERCASE**: `"STARTED"`, `"PAUSED"`, `"COMPLETED"`, `"FAILED"`, `"STOPPED"`.

The `_normalize_status()` mapping (`state_sync.py:134-154`) contains only lowercase and PascalCase entries — no UPPERCASE:

```python
mapping = {
    "idle": "Stopped", "training": "Started", "started": "Started",
    "paused": "Paused", "completed": "Completed", "failed": "Failed",
    "stopped": "Stopped", "running": "Started",
    "Stopped": "Stopped", "Started": "Started", "Paused": "Paused",
    "Completed": "Completed", "Failed": "Failed",
}
```

#### Path-Specific Behavior

| Path | `.lower()` Applied? | Status |
|------|---------------------|--------|
| Initial sync (`state_sync.py:70`) | Yes | ✅ Protected |
| Relay callback (`cascor_service_adapter.py:222`) | **No** | ❌ Vulnerable |

If CasCor sends `"STARTED"` via WebSocket, the relay callback passes it directly to `_normalize_status()`, which returns the default `"Stopped"` — incorrectly displaying a running training session as stopped.

#### Impact

- Relay-driven state updates can incorrectly set status to "Stopped" when training is running
- The `/api/state` endpoint may show incorrect status
- The status bar is **not affected** (reads from `/api/status` via fresh REST call)

#### Recommended Fix

Add `.lower()` before calling `_normalize_status()` in the relay callback:

```python
raw = data.get("status", data.get("state", ""))
status = CascorStateSync._normalize_status(raw.lower() if isinstance(raw, str) else "")
```

---

### ISSUE-6: State Sync Metrics History Stored Without Normalization

**Severity**: MODERATE
**Identified By**: Proposals v1, v2, v3, v5, v6, v7
**Category**: State Sync
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

During initial state sync, `CascorStateSync.sync()` (`state_sync.py:115-129`) stores raw CasCor metrics history directly into `SyncedState.metrics_history` without passing entries through `_normalize_metric()` or `_to_dashboard_metric()`. Raw entries use CasCor key names (`loss`, `accuracy`, `validation_loss`) instead of normalized names.

#### Current Impact

LOW — `SyncedState.metrics_history` is stored but never served to the dashboard. The dashboard polling path makes fresh REST calls that go through normalization.

#### Latent Risk

If future code serves initial metrics from synced state (e.g., to avoid cold-start empty charts), data would be in the wrong format.

#### Recommended Fix

Apply normalization during sync:

```python
state.metrics_history = [
    CascorServiceAdapter._to_dashboard_metric(
        CascorServiceAdapter._normalize_metric(m)
    )
    for m in raw_history
]
```

---

### ISSUE-7: Hardcoded localhost:8050 URLs in MetricsPanel

**Severity**: MODERATE
**Identified By**: Proposal v4
**Category**: Architecture
**Display Blocker**: No
**Validation**: ✅ CONFIRMED (6 instances)

#### Description

`MetricsPanel` contains 6 hardcoded references to `http://localhost:8050` for server-side API calls:

| Line | URL |
|------|-----|
| 1000 | `http://localhost:8050/api/network/stats` |
| 1021 | `http://localhost:8050/api/state` |
| 1155 | `http://localhost:8050/api/v1/metrics/layouts` |
| 1187 | `http://localhost:8050/api/v1/metrics/layouts` |
| 1231 | `http://localhost:8050/api/v1/metrics/layouts/{layout_name}` |
| 1274 | `http://localhost:8050/api/v1/metrics/layouts/{layout_name}` |

These are canopy self-referencing calls (Dash callback → FastAPI endpoint), not calls to cascor. They break when canopy runs on a different host, port, or behind a reverse proxy.

#### Recommended Fix

Replace with relative paths or derive from settings:

```python
requests.get(self._api_url("/api/network/stats"), timeout=2)
requests.get(self._api_url("/api/state"), timeout=2)
```

---

### ISSUE-8: Parameter Mapping Semantic Inconsistencies

**Severity**: LOW
**Identified By**: Proposals v2, v4
**Category**: Parameters
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

The `_CANOPY_TO_CASCOR_PARAM_MAP` (`cascor_service_adapter.py:357-365`) contains:

1. **`nn_growth_convergence_threshold` → `patience`**: Semantic mismatch — convergence threshold (float) vs patience count (int)
2. **`cn_training_iterations` → `candidate_epochs`**: `candidate_epochs` is **not** in cascor's `updatable_keys` set (`manager.py:545-553`), so updates are silently ignored
3. **`candidate_learning_rate`** (v4 RC-10): CasCor exposes this as updatable but canopy has no mapping or UI control

#### Recommended Fix

Review and correct semantic mappings. Add `candidate_learning_rate` to the mapping and UI if needed.

---

### ISSUE-9: Dataset Scatter Plot Empty (Metadata-Only Response)

**Severity**: MODERATE
**Identified By**: Proposal v4
**Category**: State Sync
**Display Blocker**: No
**Validation**: ✅ CONFIRMED (Known limitation)

#### Description

CasCor's dataset endpoint returns metadata only (`train_samples`, `test_samples`, `input_features`, `output_features`) without data arrays. The dashboard scatter plot requires actual data arrays to render visualizations.

#### Recommended Fix

Known limitation. Either add a paginated data endpoint to CasCor, or display "data preview unavailable in service mode" instead of empty plot.

---

### ISSUE-10: CasCor TrainingMonitor Never Updates current_phase

**Severity**: MODERATE
**Identified By**: Proposal v5
**Category**: State Sync (Cross-Repo)
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

`TrainingMonitor` in CasCor (`lifecycle/monitor.py:111`) initializes `current_phase = "output"` and **never updates it**. A comprehensive search of the cascor codebase confirms only one assignment exists (the initialization). When training enters candidate phase, `TrainingLifecycleManager` updates `training_state` (`manager.py:270: state.update_state(phase="Candidate")`) and the state machine, but NOT `monitor.current_phase`.

Since all metrics are recorded via `monitor.on_epoch_end()` which reads `self.current_phase` (line 171), **all metrics history entries have `phase: "output"` regardless of actual phase**.

#### Impact

- Phase-colored scatter plots show all data as "Output" phase
- Phase transition markers never appear on accuracy charts
- Canopy's phase-based visualization features are non-functional

#### Recommended Fix

Add a `set_phase()` method to `TrainingMonitor` and call it from the lifecycle manager during phase transitions. This is a **juniper-cascor** change.

---

### ISSUE-11: Double Initialization on Fallback-to-Demo Path

**Severity**: LOW
**Identified By**: Proposal v6
**Category**: Architecture
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

In `main.py` (lines 165-180), when the CasCor probe fails:

```python
# Line 177: In fallback block
await backend.initialize()      # First initialization

# Line 180: Unconditional
await backend.initialize()      # Second initialization
```

The demo backend gets initialized twice. This is harmless if `initialize()` is idempotent, but is a code smell.

#### Recommended Fix

Guard the second call with a flag or restructure the branching.

---

### ISSUE-12: No Single Canonical Backend Contract Across Ingress Paths

**Severity**: SYSTEMIC
**Identified By**: Proposals v6, v7
**Category**: Architecture
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

Data enters canopy from CasCor through 4 distinct ingress paths with inconsistent normalization:

| Path | Normalization | Status |
|------|---------------|--------|
| WebSocket broadcast | None — raw CasCor payloads | ❌ |
| Initial state sync | Partial — status normalized, metrics not | ⚠️ |
| HTTP polling (history) | `_normalize_metric()` applied | ✅ |
| HTTP polling (current) | `_normalize_metric()` applied | ✅ |
| Demo mode | Native canopy format | ✅ |

The fundamental issue is that `BackendProtocol` returns `Dict[str, Any]` without defining response schemas, allowing demo and service modes to silently diverge.

#### Recommended Fix

Define typed contracts (TypedDict or dataclass) for all backend response shapes. Route all ingress paths through a single normalization gateway. Add contract tests comparing demo and service output shapes.

---

### ISSUE-13: Phase 1 Tests Validate Normalization Output, Not Dashboard Compatibility

**Severity**: LOW
**Identified By**: Proposal v5
**Category**: Testing
**Display Blocker**: No
**Validation**: ✅ CONFIRMED

#### Description

Existing tests validate that `_normalize_metric()` correctly maps field names (e.g., `validation_loss` → `val_loss`) but don't verify end-to-end dashboard compatibility — i.e., that the final output matches the exact nested structure expected by MetricsPanel callbacks.

This test gap is why RC-1 persisted through Phase 1: tests confirmed flat key production, but nobody tested whether MetricsPanel could consume flat keys.

#### Recommended Fix

Add integration tests that pass CasCor-format payloads through the full pipeline and assert nested output structure matches demo mode format.

---

## 4. Retracted Issues (False Positives)

### RETRACTED-1: /api/state Parameter Initialization Uses Hardcoded Defaults

**Originally**: v1 RC-4, v3 RC-4
**Retracted By**: v1 (self-corrected during validation), v3 (self-corrected)

**Reason**: Code at `main.py:612-614` already overlays real CasCor values via `backend._adapter.get_canopy_params()`. The `setdefault()` calls only provide fallbacks when CasCor parameters are unavailable.

### RETRACTED-2: Fallback-to-Demo Path Doesn't Re-Sync training_state

**Originally**: v5 RC-6
**Retracted By**: v5 (self-corrected during validation)

**Reason**: After fallback, the lifespan function's demo-mode sync block (`main.py:183-202`) correctly syncs `training_state` from the demo backend.

---

## 5. Cross-Proposal Agreement Matrix

| Issue | v1 | v2 | v3 | v4 | v5 | v6 | v7 | Agreement |
|-------|----|----|----|----|----|----|----|----|
| ISSUE-1 (Metrics format) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7 |
| ISSUE-2 (Relay state callback) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7 |
| ISSUE-3 (HTTP polling only) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 7/7 |
| ISSUE-4 (Topology mismatch) | — | ✅ | — | ✅ | — | — | — | 2/7 |
| ISSUE-5 (Uppercase status) | — | — | — | ✅ | — | — | ✅ | 2/7 |
| ISSUE-6 (Sync metrics raw) | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | 6/7 |
| ISSUE-7 (Hardcoded URLs) | — | — | — | ✅ | — | — | — | 1/7 |
| ISSUE-8 (Param mapping) | — | ✅ | — | ✅ | — | — | — | 2/7 |
| ISSUE-9 (Dataset empty) | — | — | — | ✅ | — | — | — | 1/7 |
| ISSUE-10 (Phase never updated) | — | — | — | — | ✅ | — | — | 1/7 |
| ISSUE-11 (Double init) | — | — | — | — | — | ✅ | — | 1/7 |
| ISSUE-12 (No canonical contract) | — | — | — | — | — | ✅ | ✅ | 2/7 |
| ISSUE-13 (Test gap) | — | — | — | — | ✅ | — | — | 1/7 |

### Analysis

- **Universal consensus** (7/7): ISSUE-1, ISSUE-2, ISSUE-3 — these are the Phase 2 findings, confirmed by every proposal
- **Strong consensus** (6/7): ISSUE-6 — state sync normalization gap widely recognized
- **Specialized findings** (1-2/7): ISSUE-4, ISSUE-5, ISSUE-7, ISSUE-10 — identified only by proposals that examined paths beyond the metrics pipeline
- **Most comprehensive proposals**: v4 (11 RCs, widest scope), v2 (unique topology finding), v5 (unique cross-repo finding)

---

## 6. Fix Priority and Implementation Order

### Phase 4A — Critical Fixes (Display Blockers)

| Priority | Issue | Effort | Risk | Repo |
|----------|-------|--------|------|------|
| 1 | ISSUE-1: `_to_dashboard_metric()` | Small (1-2 hrs) | Low | juniper-canopy |
| 2 | ISSUE-4: `_transform_topology()` | Medium (2-3 hrs) | Medium | juniper-canopy |

### Phase 4B — High-Priority Fixes

| Priority | Issue | Effort | Risk | Repo |
|----------|-------|--------|------|------|
| 3 | ISSUE-5: `.lower()` in relay callback | Trivial | None | juniper-canopy |
| 4 | ISSUE-2: Forward additional relay fields | Small | Low | juniper-canopy |

### Phase 4C — Moderate-Priority Fixes

| Priority | Issue | Effort | Risk | Repo |
|----------|-------|--------|------|------|
| 5 | ISSUE-6: Normalize synced history | Small | Low | juniper-canopy |
| 6 | ISSUE-7: Replace hardcoded URLs | Trivial | None | juniper-canopy |
| 7 | ISSUE-10: Update monitor phase | Small | Low | **juniper-cascor** |

### Phase 4D — Low-Priority / Future

| Priority | Issue | Effort | Risk | Repo |
|----------|-------|--------|------|------|
| 8 | ISSUE-8: Fix param mappings | Small | Low | juniper-canopy |
| 9 | ISSUE-11: Guard double init | Trivial | None | juniper-canopy |
| 10 | ISSUE-13: Add contract tests | Medium | None | juniper-canopy |
| 11 | ISSUE-12: Define typed contracts | Large | Moderate | juniper-canopy |
| 12 | ISSUE-9: Dataset data arrays | Large | Moderate | juniper-cascor |
| 13 | ISSUE-3: WebSocket consumption | Large | Moderate | juniper-canopy |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `_to_dashboard_metric()` introduces None values | Medium | Low | Dashboard `.get("loss", 0)` falls back to 0 |
| Topology weight ordering assumption incorrect | Medium | Medium | Verify against cascor's actual serialization |
| Demo mode regresses from normalization changes | Low | High | Demo path untouched; normalizers are separate |
| Multiple simultaneous fixes introduce regressions | Medium | Medium | Fix and test one issue at a time |
| FakeCascorClient divergence masks new issues | High | Medium | Add integration tests with real response shapes |
| Phase 1 test assertions need updating | High | Low | Update test expectations to nested format |

---

## 8. Verification Plan

### 8.1 Automated Tests

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython

# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v -m "not requires_cascor"

# Regression tests
pytest tests/regression/ -v

# Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### 8.2 Manual Integration Test

```bash
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# Terminal 2: Start canopy (service mode)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: Verify API responses
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, "phase": "...", ...}]}

curl -s http://localhost:8050/api/topology | python3 -m json.tool
# Expected: {"input_units": 2, "output_units": 1, "hidden_units": N,
#            "nodes": [...], "connections": [...]}

curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 8.3 Visual Verification Checklist

- [ ] Loss chart displays live training data (not flat line at 0)
- [ ] Accuracy chart displays accuracy curve
- [ ] Current loss display shows actual value (not "0.0000")
- [ ] Current accuracy display shows actual percentage (not "0.00%")
- [ ] Hidden units count shows actual count (not always 0)
- [ ] Hidden unit addition markers appear on plots
- [ ] Network graph shows input/hidden/output nodes with connections
- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Phase indicator shows Output/Candidate transitions
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and shows correct metrics

---

## 9. Files Requiring Modification

### juniper-canopy

| File | Issues | Changes |
|------|--------|---------|
| `src/backend/cascor_service_adapter.py` | 1, 2, 4, 5 | Add `_to_dashboard_metric()`, `_transform_topology()`, fix relay callback |
| `src/backend/state_sync.py` | 6 | Normalize metrics history during sync |
| `src/frontend/components/metrics_panel.py` | 7 | Replace 6 hardcoded localhost URLs |
| `src/main.py` | 11 | Guard double initialization |

### juniper-cascor

| File | Issues | Changes |
|------|--------|---------|
| `src/api/lifecycle/monitor.py` | 10 | Add `set_phase()` method |
| `src/api/lifecycle/manager.py` | 10 | Call `monitor.set_phase()` on transitions |

### Files NOT requiring modification

- `metrics_panel.py` (for ISSUE-1) — fix is in backend, not the panel
- `dashboard_manager.py` — callbacks are correct; data they receive is wrong
- `demo_mode.py` — demo format is the target format
- `network_visualizer.py` — fix is in adapter, not the visualizer

---

## 10. Conclusions

1. **Phase 2 correctly identified the primary blocker** (ISSUE-1, metrics format mismatch). All 7 proposals unanimously confirmed this finding. This is the single most important fix.

2. **Two critical display blockers exist**: ISSUE-1 (metrics) and ISSUE-4 (topology). Fixing both will restore full dashboard functionality for external CasCor connections.

3. **Phase 2's scope was too narrow**: It focused exclusively on the metrics panel data path. The topology visualization (ISSUE-4), status normalization (ISSUE-5), and cross-repo phase tracking (ISSUE-10) were not examined.

4. **The most comprehensive proposals** were v4 (11 root causes, widest scope including deployment concerns) and v2 (unique topology format discovery that is a display blocker).

5. **The most valuable unique finding** was v5's discovery that CasCor's `TrainingMonitor.current_phase` is never updated — a cross-repo issue that no other proposal identified.

6. **The fundamental architectural cause** underlying all issues (identified by v6, v7) is the absence of typed data contracts between backend and frontend. `BackendProtocol` returns `Dict[str, Any]`, allowing demo and service modes to silently diverge.

7. **All 7 proposals agreed on the fix approach** for ISSUE-1: add `_to_dashboard_metric()` as a second transformation layer after `_normalize_metric()`.

---

## Appendix A: Proposal Cross-Reference

| Issue | v1 RC | v2 RC | v3 RC | v4 RC | v5 RC | v6 RC | v7 RC |
|-------|-------|-------|-------|-------|-------|-------|-------|
| ISSUE-1 | RC-1 | RC-1 | RC-1 | RC-1 | RC-1 | RC-1 | RC-1 |
| ISSUE-2 | RC-2 | RC-2 | RC-2 | RC-2 | RC-2 | RC-2 | RC-2 |
| ISSUE-3 | RC-3 | RC-3 | RC-3 | RC-3 | RC-3 | RC-3 | RC-3 |
| ISSUE-4 | — | RC-4 | — | RC-5 | — | — | — |
| ISSUE-5 | — | — | — | RC-4 | — | — | RC-4 |
| ISSUE-6 | RC-5 | RC-5 | RC-5 | — | RC-4 | RC-4 | RC-5 |
| ISSUE-7 | — | — | — | RC-7 | — | — | — |
| ISSUE-8 | — | RC-6 | — | RC-9, RC-10 | — | — | — |
| ISSUE-9 | — | — | — | RC-6 | — | — | — |
| ISSUE-10 | — | — | — | — | RC-5 | — | — |
| ISSUE-11 | — | — | — | — | — | RC-6 | — |
| ISSUE-12 | — | — | — | — | — | RC-7 | RC-7 |
| ISSUE-13 | — | — | — | — | RC-7 | — | — |

## Appendix B: Document Lineage

```text
Phase 0 (Original Analysis):
  CANOPY_EXTERNAL_CASCOR_PLAN.md
  CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md

Phase 1 (Development Plans — Implemented):
  MERGED_EXTERNAL_CASCOR_DEV_PLAN.md
  UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md
  DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md
  EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md

Phase 2 (Root Cause Analysis):
  ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md

Phase 3 (Independent Proposals):
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v1.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v2.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v3.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v4.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v5.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v6.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v7.md

Phase 4 (Synthesis — This Document):
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_002192f3-fbde-444b-ac3f-2c0e6ceb8f96.md
```
