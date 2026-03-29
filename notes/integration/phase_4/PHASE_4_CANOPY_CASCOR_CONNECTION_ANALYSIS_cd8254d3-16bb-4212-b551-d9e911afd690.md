# Phase 4 Comprehensive Analysis: Canopy-CasCor External Connection Failure

- **Version**: 1.0.0
- **Date**: 2026-03-27
- **Author**: Amp (AI Agent)
- **Status**: Analysis Complete — Synthesized, Validated, Finalized
- **UUID**: cd8254d3-16bb-4212-b551-d9e911afd690
- **Source Material**: 7 independent Phase 3 proposals (v1–v7), Phase 1 development plan, Phase 2 root cause analysis
- **Repositories Analyzed**: juniper-canopy, juniper-cascor, juniper-cascor-client
- **Validation**: All findings independently verified against current codebase HEAD by specialized sub-agents

---

## 1. Executive Summary

This document synthesizes, integrates, and validates the findings from seven independent Phase 3 proposals investigating the persistent failure of juniper-canopy's dashboard to display training data from an externally running juniper-cascor service instance. All proposals were cross-referenced against the current codebase to eliminate false positives and confirm genuine root causes.

### Consolidated Root Cause Registry

| ID       | Severity     | Root Cause                                                                         | Proposals Identifying  | Validation Status                  |
|----------|--------------|------------------------------------------------------------------------------------|------------------------|------------------------------------|
| **RC-1** | **CRITICAL** | Metrics format mismatch: service produces flat keys, dashboard reads nested keys   | All 7 (v1–v7)         | **CONFIRMED** — Primary blocker   |
| **RC-2** | MODERATE     | WebSocket relay state callback omits fields (only sends status + phase)            | All 7 (v1–v7)         | **CONFIRMED** — Root cause upstream |
| **RC-3** | LOW          | Dashboard uses HTTP polling exclusively, ignoring WebSocket relay                  | All 7 (v1–v7)         | **CONFIRMED** — Not a blocker     |
| **RC-4** | MODERATE     | Network topology format mismatch (`input_size`/`output_size` vs `input_units`/`output_units`) | v2, v4               | **CONFIRMED**                      |
| **RC-5** | MODERATE     | Uppercase status normalization gap in relay path (missing `.lower()`)              | v4, v7                | **CONFIRMED as LATENT** — CasCor currently broadcasts title-case, not UPPERCASE |
| **RC-6** | MODERATE     | State sync `metrics_history` stored raw without normalization                      | v1, v3, v5, v6, v7    | **CONFIRMED** — Latent bug        |
| **RC-7** | LOW          | Hardcoded `localhost:8050` URLs in MetricsPanel                                    | v4                    | **CONFIRMED**                      |
| **RC-8** | LOW          | WebSocket relay broadcasts unnormalized metric field names                         | v4, v7                | **CONFIRMED** — Latent             |
| **RC-9** | LOW          | Dead parameter mapping: `cn_training_iterations` → `candidate_epochs`             | v2, v4                | **CONFIRMED**                      |
| **RC-10**| LOW          | `candidate_learning_rate` updatable on cascor but unmapped in canopy               | v4                    | **CONFIRMED**                      |
| **RC-11**| LOW          | Double initialization on fallback-to-demo path in `main.py`                       | v6                    | **CONFIRMED**                      |
| **RC-12**| LOW          | CasCor `TrainingMonitor.current_phase` never updated after init                   | v5                    | **CONFIRMED** — cascor-side bug    |
| **RC-13**| LOW          | Phase 1 test coverage gap: tests validate flat output, not dashboard compatibility | v5                    | **CONFIRMED**                      |
| **RC-14**| INFO         | Dual status normalization paths produce inconsistent representations               | v4                    | **CONFIRMED** — Architectural note |
| **RC-15**| **SYSTEMIC** | No single canonical metric contract enforced across all ingress paths              | v6, v7                | **CONFIRMED** — Architectural root cause |

### Known Limitations (Not Bugs)

| ID | Severity | Limitation | Proposals Identifying | Notes |
|----|----------|------------|----------------------|-------|
| KL-1 | MODERATE | Dataset scatter plot always empty in service mode — CasCor returns metadata only, not data arrays | v4 | Architectural limitation of the cascor API; requires cascor API extension or direct juniper-data integration to resolve |

### Rejected / Subsumed Findings

| Proposed RC | Source  | Claim                                                       | Validation Result                                      |
|-------------|---------|-------------------------------------------------------------|--------------------------------------------------------|
| v1-RC-4     | v1, v3  | `/api/state` parameter initialization uses hardcoded defaults | **FALSE POSITIVE** — `main.py:612-614` overlays live cascor values via `get_canopy_params()` |
| v5-RC-6     | v5      | Fallback-to-demo path doesn't re-sync `training_state`       | **RETRACTED by author** — validation proved state sync executes correctly after fallback |
| v6-RC-5     | v6      | `/api/metrics` (current snapshot) returns flat format        | **SUBSUMED by RC-1** — `get_current_metrics()` calls `_normalize_metric()` at line 91, producing the same flat format as the history path. The RC-1 fix (`_to_dashboard_metric()`) must also be applied here. Not a separate root cause but a second code path affected by the same bug. |
| v2-RC-6 (semantics) | v2 | `patience` → `nn_growth_convergence_threshold` semantic mismatch | **CONFIRMED** but reclassified as part of RC-9 (parameter mapping issues) |

---

## 2. Methodology

### 2.1 Synthesis Process

1. All 7 proposals were read in their entirety and cataloged by root cause
2. Each distinct issue was cross-referenced across all proposals to identify consensus and divergence
3. Issues identified by multiple proposals were synthesized to produce the most complete description
4. Issues identified by only one proposal were independently validated against the codebase
5. Four specialized validation sub-agents verified all claims against current source code
6. False positives were identified and documented with evidence for rejection

### 2.2 Proposal Coverage Matrix

| Root Cause | v1 | v2 | v3 | v4 | v5 | v6 | v7 | Consensus |
|------------|----|----|----|----|----|----|----|-----------|
| RC-1 (metrics flat vs nested) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 — unanimous |
| RC-2 (relay omits fields) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 — unanimous |
| RC-3 (polling vs WebSocket) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 — unanimous |
| RC-4 (topology format) | | ✓ | | ✓ | | | | 2/7 |
| RC-5 (uppercase status) | | | | ✓ | | | ✓ | 2/7 |
| RC-6 (raw synced metrics) | ✓ | | ✓ | | ✓ | ✓ | ✓ | 5/7 |
| RC-7 (hardcoded URLs) | | | | ✓ | | | | 1/7 |
| RC-8 (relay raw metrics) | | | | ✓ | | | ✓ | 2/7 |
| RC-9 (dead param mapping) | | ✓ | | ✓ | | | | 2/7 |
| RC-10 (unmapped candidate_lr) | | | | ✓ | | | | 1/7 |
| RC-11 (double init) | | | | | | ✓ | | 1/7 |
| RC-12 (cascor phase stuck) | | | | | ✓ | | | 1/7 |
| RC-13 (test gap) | | | | | ✓ | | | 1/7 |
| RC-14 (dual normalization) | | | | ✓ | | | | 1/7 |
| RC-15 (no canonical contract) | | | | | | ✓ | ✓ | 2/7 |
| FALSE: `/api/state` defaults | ✓ | | ✓ | | | | | 2/7 — disproven |
| FALSE: fallback re-sync | | | | | ✓ | | | 1/7 — retracted |
| FALSE: `/api/metrics` flat | | | | | | ✓ | | 1/7 — disproven |

---

## 3. Phase 1 and Phase 2 Evaluation

### 3.1 Phase 1 Assessment (Unanimous Across All 7 Proposals)

All 7 proposals confirmed that:

- **All 14 fixes (FIX-1 through FIX-14, plus FIX-SYS) are correctly implemented** in the current codebase
- The fixes successfully resolved the ResponseEnvelope unwrapping problem
- The foundational diagnosis was correct: `_ServiceTrainingMonitor` and `CascorStateSync` were developed against `FakeCascorClient` whose format diverged from the real server

**Where Phase 1 went wrong** (unanimous across all 7 proposals):

The plan defined a "Canonical Internal Contract" (Section 6.2) with **flat** keys (`train_loss`, `train_accuracy`, `hidden_units`). This contract was designed by analyzing the normalization boundary (cascor → canopy) but was **never validated against the dashboard's actual input format** (the nested format that demo mode produces: `metrics.loss`, `network_topology.hidden_units`). The status bar worked because it reads flat keys, creating false confidence that the contract was correct.

### 3.2 Phase 2 Assessment (Confirmed by All 7 Proposals)

| Phase 2 Finding | All 7 Proposals |
|----------------|----------------|
| RC-1 correctly identified as CRITICAL | ✅ Unanimous |
| RC-2 correctly identified as MODERATE | ✅ Unanimous |
| RC-3 correctly identified as LOW | ✅ Unanimous |
| Fix recommendation (Option A: normalize at service backend) is correct | ✅ Unanimous |
| All Phase 1 fixes verified as implemented | ✅ Unanimous |

**Phase 2 limitations** (consensus from proposals):

- Scope was too narrow — focused on metrics panel only (v2, v4, v7)
- Did not examine topology, parameter mapping, or state sync paths (v2, v4)
- Identified the symptom correctly but did not elevate to architectural root cause (v6, v7)

---

## 4. Root Cause Detail: RC-1 — Metrics Format Mismatch

**Severity**: CRITICAL
**Identified by**: All 7 proposals (unanimous)
**Validation**: CONFIRMED by codebase verification

### 4.1 Description

The service backend's `_normalize_metric()` (`cascor_service_adapter.py:439-460`) produces metrics in a **flat** dictionary format:

```python
{"epoch": 1, "train_loss": 0.5, "train_accuracy": 0.7, "val_loss": 0.6, "val_accuracy": 0.65, "hidden_units": 0, "phase": "output", "timestamp": "..."}
```

The dashboard's `MetricsPanel` (`metrics_panel.py`) reads metrics using **nested** dictionary access at 9 confirmed locations:

```python
m.get("metrics", {}).get("loss", 0)              # lines 1120, 1330
m.get("metrics", {}).get("accuracy", 0)           # lines 1121, 1499
m.get("network_topology", {}).get("hidden_units", 0)  # lines 1091, 1122, 1449, 1450, 1561-1562
```

Demo mode (`demo_mode.py:1162-1177`) produces the **nested** format the dashboard expects:

```python
{"epoch": N, "metrics": {"loss": ..., "accuracy": ..., "val_loss": ..., "val_accuracy": ...},
 "network_topology": {"input_units": ..., "hidden_units": ..., "output_units": ...},
 "phase": "...", "timestamp": "..."}
```

### 4.2 Complete Data Flow Trace (Service Mode)

```
Step 1: CasCor TrainingMonitor.on_epoch_end()
        → {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase, timestamp}
Step 2: Wrapped in ResponseEnvelope: {"status": "success", "data": [...], "meta": {...}}
Step 3: JuniperCascorClient.get_metrics_history() → returns raw response.json()
Step 4: _ServiceTrainingMonitor.get_recent_metrics() → unwraps envelope → _normalize_metric()
        → FLAT: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units, phase}
Step 5: ServiceBackend.get_metrics_history() → passes through unchanged
Step 6: main.py /api/metrics/history → {"history": [flat_dicts]}
Step 7: dashboard_manager → extracts list into metrics-panel-metrics-store
Step 8: MetricsPanel reads:
        metric.get("metrics", {}).get("loss", 0) → {}.get("loss", 0) → ALWAYS 0
        metric.get("network_topology", {}).get("hidden_units", 0) → ALWAYS 0
```

### 4.3 Field Name Mapping Detail (v1, v3 nuance)

The field name mapping between flat and nested formats is non-trivial — the `train_` prefix must be stripped when nesting:

| Flat Key (from `_normalize_metric`) | Required Nested Path (from dashboard) | Notes |
|-------------------------------------|---------------------------------------|-------|
| `train_loss` | `metrics.loss` | Strip `train_` prefix |
| `train_accuracy` | `metrics.accuracy` | Strip `train_` prefix |
| `val_loss` | `metrics.val_loss` | Same name |
| `val_accuracy` | `metrics.val_accuracy` | Same name |
| `hidden_units` | `network_topology.hidden_units` | Move into nested dict |

### 4.4 Impact

- **Loss chart**: All y-values read as `0` → flat line at zero or empty plot
- **Accuracy chart**: All y-values read as `0` → flat line at zero or empty plot
- **Current loss/accuracy displays**: Always show "0.0000" / "0.00%" or "--"
- **Hidden units count (metrics panel)**: Always shows `0`
- **Hidden unit addition markers**: Never rendered (change detection always sees 0→0)

### 4.5 Why Phase 1 Missed This (Root Cause of the Root Cause)

All 7 proposals agree: The Phase 1 plan's "Canonical Internal Contract" was designed by analyzing what cascor sends and what canopy should normalize to. It was never validated against what the dashboard actually reads. The status bar (which reads flat keys) worked, creating false confidence that flat keys were the correct target. But the MetricsPanel was built against demo mode's nested format — a different contract entirely.

### 4.6 Recommended Fix

**Unanimous recommendation across all 7 proposals**: Add `_to_dashboard_metric()` transformation.

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

**Apply in**: `_ServiceTrainingMonitor.get_recent_metrics()` and `get_current_metrics()`, wrapping results after `_normalize_metric()`.

**Advantages** (synthesized from all proposals):
- Single transformation point — all metrics pass through one function
- Preserves the existing normalization layer separation of concerns
- Dashboard code untouched — no changes to 9+ MetricsPanel locations
- Demo mode path unaffected
- Each layer independently testable
- Minimal blast radius

**Risks**:
- LOW: Must preserve falsy-but-valid values (epoch=0, loss=0.0) — `_first_defined()` helper already handles this
- LOW: `network_topology` dict in service mode would only have `hidden_units`, missing `input_units` and `output_units` — but dashboard currently only reads `hidden_units`

---

## 5. Root Cause Detail: RC-2 — WebSocket Relay Omits Fields

**Severity**: MODERATE
**Identified by**: All 7 proposals (unanimous)
**Validation**: CONFIRMED — with upstream root cause clarification

### 5.1 Description

The WebSocket relay callback (`cascor_service_adapter.py:222-223`) only forwards `status` and `phase` to the global `training_state`:

```python
status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
self._state_update_callback(status=status, phase=data.get("phase", ""))
```

### 5.2 Validation Clarification

Independent validation revealed an important nuance **not identified by any of the 7 proposals**: The actual CasCor WebSocket state broadcast (`manager.py` line 111) sends only a minimal dict:

```python
create_state_message({"status": "Started", "phase": "Output"})
```

This means the relay callback isn't actually discarding fields from the wire — CasCor itself doesn't send `current_epoch`, `learning_rate`, etc. over WebSocket. The upstream root cause is that CasCor's `_register_ws_callbacks()` broadcasts a minimal state dict rather than the full `training_state.get_state()`.

### 5.3 Impact

- The `/api/state` endpoint reads from `training_state.get_state()`, which only receives `status` and `phase` via relay
- After initial sync, `current_epoch` in `training_state` becomes stale
- **Mitigating factor** (confirmed by all 7 proposals): The status bar reads from `/api/status` which makes a fresh REST call on each poll, bypassing stale `training_state`

### 5.4 Recommended Fix (Synthesized)

**Two-part fix** (combining relay-side and cascor-side):

1. **Relay side** — expand the callback to forward any additional fields present:

```python
self._state_update_callback(
    status=status,
    phase=data.get("phase", ""),
    current_epoch=data.get("current_epoch"),
    learning_rate=data.get("learning_rate"),
    max_hidden_units=data.get("max_hidden_units"),
    max_epochs=data.get("max_epochs"),
)
```

`TrainingState.update_state()` silently ignores `None` values, so passing fields not present in the message is safe.

2. **CasCor side** (future enhancement) — consider broadcasting the full `training_state.get_state()` dict from `_register_ws_callbacks()` instead of a minimal dict.

---

## 6. Root Cause Detail: RC-3 — Dashboard Ignores WebSocket Relay

**Severity**: LOW
**Identified by**: All 7 proposals (unanimous)
**Validation**: CONFIRMED — Not a functional blocker

### 6.1 Description

The dashboard uses HTTP polling exclusively via `dcc.Interval` callbacks:

| Interval ID | Period | Feeds |
|-------------|--------|-------|
| `fast-update-interval` | 1000ms | Status bar, metrics store |
| `slow-update-interval` | 5000ms | Topology, dataset, decision boundary |

A `websocket-data` div exists in the layout (`dashboard_manager.py:876`) but no Dash callback reads from it.

### 6.2 Recommendation

Future enhancement — not a blocker. HTTP polling at 1-second intervals is adequate for training progress display. If real-time updates are desired, implement Dash clientside callbacks or use `dash_extensions.WebSocket`.

---

## 7. Root Cause Detail: RC-4 — Topology Format Mismatch

**Severity**: MODERATE
**Identified by**: v2, v4
**Validation**: CONFIRMED

### 7.1 Description

CasCor's `/v1/network/topology` endpoint returns a **weight-oriented** structure:

```python
{
    "input_size": int,        # Key: input_size (not input_units)
    "output_size": int,       # Key: output_size (not output_units)
    "hidden_units": [         # TYPE: array of unit objects (not integer count)
        {"id": int, "weights": [float, ...], "bias": float, "activation": str},
    ],
    "output_weights": [[float, ...], ...],
    "output_bias": [float, ...]
}
```

The `NetworkVisualizer` (`network_visualizer.py:577-579`) expects a **graph-oriented** structure:

```python
{
    "input_units": int,       # Key: input_units
    "output_units": int,      # Key: output_units
    "hidden_units": int,      # TYPE: integer count
    "connections": [{"from": "input_0", "to": "hidden_0", "weight": 0.5}, ...],
    "nodes": [{"id": "input_0", "type": "input", "layer": 0}, ...]
}
```

### 7.2 Evidence

| Aspect | CasCor Server | NetworkVisualizer | Match? |
|--------|--------------|-------------------|--------|
| Input count key | `input_size` | `input_units` | **No** |
| Output count key | `output_size` | `output_units` | **No** |
| Hidden units type | Array of unit objects | Integer count | **No** |
| Connection list | Not present | Required: `[{from, to, weight}]` | **No** |
| Node list | Not present | Optional: `[{id, type, layer}]` | **No** |

The adapter's `extract_network_topology()` (`cascor_service_adapter.py:480-484`) is a raw pass-through — it only unwraps the ResponseEnvelope and does no structural transformation.

The validation guard at `network_visualizer.py:344-346` checks `topology_data.get("input_units", 0) == 0` — since cascor returns `input_size` (not `input_units`), this always evaluates to `0`, displaying an empty graph.

### 7.3 Recommended Fix (Synthesized from v2)

Add a `_transform_topology()` method in `CascorServiceAdapter` that converts the weight-oriented format to the graph-oriented format, including:

- Key remapping: `input_size` → `input_units`, `output_size` → `output_units`
- `hidden_units` array → integer count
- Reconstructing `nodes` and `connections` arrays from weight data
- Cascade architecture awareness (each hidden unit connects to all inputs AND all prior hidden units)

---

## 8. Root Cause Detail: RC-5 — Uppercase Status Normalization Gap

**Severity**: MODERATE (LATENT)
**Identified by**: v4, v7
**Validation**: CONFIRMED as LATENT defect

### 8.1 Description

The relay callback at `cascor_service_adapter.py:222` passes raw status strings to `_normalize_status()` without calling `.lower()`:

```python
status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
```

The `_normalize_status()` mapping (`state_sync.py:137-153`) has lowercase and title-case keys but **no uppercase keys** (no `"STARTED"`, `"PAUSED"`, etc.).

### 8.2 Validation Nuance

Independent validation revealed that while CasCor's `TrainingStateMachine.get_state_summary()` uses `.name` on Python enums (producing UPPERCASE), the actual WebSocket broadcast uses **hardcoded title-case** strings:

```python
create_state_message({"status": "Started", "phase": "Output"})
```

This means the uppercase normalization gap is **not currently triggered** — but it becomes active if CasCor is ever changed to broadcast the full state summary (which uses `.name` → UPPERCASE).

### 8.3 Contrast with Working Paths

The initial sync path (`state_sync.py:70`) **does** call `.lower()` before `_normalize_status()`. The REST status path (`service_backend.py:108`) uses its own `.upper()` comparison chain. Only the relay path lacks case normalization.

### 8.4 Recommended Fix

Add `.lower()` before `_normalize_status()` in the relay callback:

```python
raw = data.get("status", data.get("state", ""))
status = CascorStateSync._normalize_status(raw.lower() if isinstance(raw, str) else "")
```

---

## 9. Root Cause Detail: RC-6 — State Sync Metrics Not Normalized

**Severity**: MODERATE (LATENT)
**Identified by**: v1, v3, v5, v6, v7 (5 of 7 proposals)
**Validation**: CONFIRMED

### 9.1 Description

`CascorStateSync.sync()` (`state_sync.py:115-129`) stores raw cascor metrics history directly into `state.metrics_history` without any normalization:

```python
state.metrics_history = data  # Raw cascor format — NOT normalized
```

The raw data uses cascor's native field names (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`) — different from both the canonical flat format (`train_loss`, `train_accuracy`) AND the dashboard's nested format (`metrics.loss`).

### 9.2 Current Impact

**None** — `synced.metrics_history` is currently unused for dashboard display. `ServiceBackend.get_metrics_history()` always fetches fresh data via `_ServiceTrainingMonitor.get_recent_metrics()`, which applies normalization.

### 9.3 Latent Risk

If a future code path (e.g., pre-populating the metrics store on connect to avoid a brief blank display) reads `synced.metrics_history`, it would receive data in the wrong format. As v3 notes, this is a "double latent issue" — even normalizing the synced history via `_normalize_metric()` would still produce flat keys without the `_to_dashboard_metric()` transformation.

### 9.4 Recommended Fix

Apply both normalization steps to synced metrics:

```python
from backend.cascor_service_adapter import CascorServiceAdapter

state.metrics_history = [
    CascorServiceAdapter._to_dashboard_metric(
        CascorServiceAdapter._normalize_metric(m)
    )
    for m in raw_history
]
```

---

## 10. Root Cause Detail: RC-7 — Hardcoded Localhost URLs

**Severity**: LOW
**Identified by**: v4
**Validation**: CONFIRMED

### 10.1 Description

Two HTTP requests in `metrics_panel.py` use hardcoded `http://localhost:8050` instead of dynamically constructed URLs:

| Line | Code |
|------|------|
| 1000 | `requests.get("http://localhost:8050/api/network/stats", timeout=2)` |
| 1021 | `requests.get("http://localhost:8050/api/state", timeout=2)` |

All other callbacks use `self._api_url(path)` which dynamically determines the host.

### 10.2 Impact

When canopy runs in Docker, behind a reverse proxy, or on a non-standard host/port, these requests fail silently with `ConnectionError` (caught and logged). Network stats and training state panels in the metrics component return fallback/empty data.

### 10.3 Recommended Fix

Replace hardcoded URLs with `self._api_url("/api/network/stats")` and `self._api_url("/api/state")`.

---

## 11. Root Cause Detail: RC-8 — Relay Broadcasts Unnormalized Metrics

**Severity**: LOW (LATENT)
**Identified by**: v4, v7
**Validation**: CONFIRMED

### 11.1 Description

The relay loop (`cascor_service_adapter.py:203-206`) broadcasts raw CasCor WebSocket messages without applying `_normalize_metric()`:

```python
async for message in stream.stream():
    msg_type = message.get("type", "")
    data = message.get("data", message)
    await websocket_manager.broadcast({"type": msg_type, "data": data})
```

CasCor's metrics messages use raw field names (`loss`, `accuracy`, `validation_loss`). The REST polling path normalizes these to `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`.

### 11.2 Current Impact

None — the dashboard doesn't consume WebSocket data (RC-3). This becomes a bug only if RC-3 is addressed.

### 11.3 Recommended Fix

If/when WebSocket consumption is implemented, apply `_normalize_metric()` and `_to_dashboard_metric()` to relay `metrics` type messages before broadcasting.

---

## 12. Root Cause Detail: RC-9 — Dead Parameter Mapping

**Severity**: LOW
**Identified by**: v2, v4
**Validation**: CONFIRMED

### 12.1 Description

Two parameter mapping issues exist:

**Issue 9a**: `cn_training_iterations` → `candidate_epochs` (`cascor_service_adapter.py:364`)

CasCor's `get_training_params()` (`manager.py:511-522`) returns 6 keys: `learning_rate`, `max_hidden_units`, `epochs_max`, `patience`, `candidate_pool_size`, `correlation_threshold`. It does **not** return `candidate_epochs`. The mapping target is unreachable — `cn_training_iterations` always shows its default value and writes are silently dropped.

**Issue 9b**: `patience` → `nn_growth_convergence_threshold` semantic mismatch (`cascor_service_adapter.py:361`)

`patience` is an integer epoch count (number of epochs to wait before stopping); `nn_growth_convergence_threshold` semantically suggests a float threshold value. The mapping works mechanically but the UI label is misleading.

### 12.2 Recommended Fix

- Remove or correct the dead `candidate_epochs` mapping
- Rename the canopy parameter label to match the semantic meaning of `patience`, or add a separate `nn_patience` parameter

---

## 13. Root Cause Detail: RC-10 — Unmapped `candidate_learning_rate`

**Severity**: LOW
**Identified by**: v4
**Validation**: CONFIRMED

### 13.1 Description

CasCor's `PATCH /v1/training/params` accepts `candidate_learning_rate` as an updatable field (`routes/training.py:45-54`), but the `_CANOPY_TO_CASCOR_PARAM_MAP` has no entry mapping any canopy parameter to `candidate_learning_rate`.

### 13.2 Recommended Fix

Add a `cn_candidate_learning_rate` → `candidate_learning_rate` mapping entry.

---

## 14. Root Cause Detail: RC-11 — Double Initialization on Fallback

**Severity**: LOW
**Identified by**: v6
**Validation**: CONFIRMED

### 14.1 Description

In `main.py`, when the cascor probe fails and the backend falls back to demo mode:

1. `backend.initialize()` is called at line 177 (inside the fallback block)
2. `backend.initialize()` is called again at line 180 (unconditionally)

### 14.2 Impact

For `DemoBackend`, `initialize()` calls `self._demo.start()`, which starts the training simulation thread. Calling it twice could start two simulation threads depending on idempotency guarantees. This only affects the fallback-to-demo path and is not related to the external cascor display problem.

### 14.3 Recommended Fix

Guard the unconditional initialization:

```python
initialized = False
if cascor_url and backend.backend_type == "service":
    # ... probe logic ...
    if not healthy:
        backend = create_backend(demo_mode=True)
        await backend.initialize()
        initialized = True

if not initialized:
    await backend.initialize()
```

---

## 15. Root Cause Detail: RC-12 — CasCor Phase Never Updated in Monitor

**Severity**: LOW
**Identified by**: v5
**Validation**: CONFIRMED — cascor-side bug

### 15.1 Description

CasCor's `TrainingMonitor.current_phase` is initialized to `"output"` (`monitor.py:111`) and **never reassigned**. The `TrainingLifecycleManager` updates `TrainingState._phase` via `state.update_state(phase="Candidate")` at `manager.py:270`, but does not update `monitor.current_phase`.

Since `on_epoch_end()` reads `self.current_phase` (`monitor.py:171`) when recording metrics, **all metrics history entries have `phase: "output"` regardless of actual training phase**.

### 15.2 Impact on Canopy

- Phase-colored scatter plots show all data as "Output Training" — no "Candidate Training" data
- The dashboard uses substring matching (`"output" in phase`, `"candidate" in phase`) for phase filtering — candidate data will never appear
- This is a **cascor-side bug**, not a canopy bug

### 15.3 Recommended Fix

In `juniper-cascor/src/api/lifecycle/manager.py`, update `monitor.current_phase` when phase transitions occur (alongside the existing `state.update_state(phase=...)` calls).

---

## 16. Root Cause Detail: RC-13 — Test Coverage Gap

**Severity**: LOW
**Identified by**: v5
**Validation**: CONFIRMED

### 16.1 Description

Phase 1 characterization tests (`tests/unit/test_response_normalization.py`) validate that normalization produces correct flat output (e.g., `"train_loss" in result[0]`) but never verify compatibility with the dashboard's expected nested format.

This test coverage gap is the reason RC-1 persisted through the entire Phase 1 development cycle. The tests confirmed that `_normalize_metric()` worked as designed, but the design itself was wrong (flat instead of nested).

### 16.2 Recommended Fix

Add end-to-end contract tests comparing service mode output structure against demo mode output structure:

```python
def test_metrics_history_contract_matches_demo():
    """Service mode metrics must use same nested format as demo mode."""
    service_metric = service_backend.get_metrics_history(1)[0]
    assert "metrics" in service_metric, "Missing nested 'metrics' key"
    assert "network_topology" in service_metric, "Missing nested 'network_topology' key"
    assert "loss" in service_metric["metrics"], "Missing metrics.loss"
```

---

## 17. Root Cause Detail: RC-14 — Dual Status Normalization

**Severity**: INFO
**Identified by**: v4
**Validation**: CONFIRMED — architectural observation

### 17.1 Description

Two independent normalization paths produce different string representations of the same cascor status:

- **Path A** (`ServiceBackend.get_status()` via `service_backend.py:107-115`): Uses `.upper()` comparison, returns boolean flags (`is_running`, `is_paused`) plus raw `fsm_status`
- **Path B** (relay callback via `CascorStateSync._normalize_status()`): Returns title-case strings (`"Started"`, `"Paused"`, `"Completed"`)

`training_state` (Path B) holds `status="Started"` while `/api/status` (Path A) returns `is_running=True` and `fsm_status="STARTED"`. Not a functional blocker but increases coupling fragility.

---

## 18. Root Cause Detail: RC-15 — No Canonical Backend Contract

**Severity**: SYSTEMIC
**Identified by**: v6, v7
**Validation**: CONFIRMED — architectural root cause

### 18.1 Description

This is the deepest root cause underlying RC-1, RC-4, RC-6, RC-8, and the Phase 1 plan's failure. The system has **mode-dependent data schemas** — different data paths produce different shapes for the same information:

| Data Path | Data Shape | Matches Dashboard? |
|-----------|-----------|-------------------|
| Demo mode metrics history | Nested (`metrics.loss`) | ✅ Yes |
| Service mode metrics history | Flat (`train_loss`) | ❌ No |
| Service mode status | Flat (`is_running`) | ✅ Yes |
| Service mode state sync | Raw CasCor format | ❌ No |
| Service mode relay broadcast | Raw CasCor format | ❌ No |

There is **no shared function or contract** enforcing all paths to produce the same output shape. `BackendProtocol` returns `Dict[str, Any]` for all methods, allowing demo mode and service mode to silently diverge in output formats.

### 18.2 Recommended Architectural Fix

1. Create a single shared metric formatter that accepts any known input format and produces the nested format
2. Route ALL metric ingress paths through this formatter
3. Define TypedDict or dataclass contracts for `BackendProtocol` return types
4. Add contract tests comparing demo and service payload shapes

---

## 19. What Works Correctly (Verified)

For completeness, these data paths function correctly in the current codebase:

| Data Path | Status | Evidence |
|-----------|--------|----------|
| **Status bar** (is_running, phase, epoch, hidden units) | ✅ Working | `ServiceBackend.get_status()` transforms nested→flat correctly; fresh REST call each poll |
| **Decision boundary** visualization | ✅ Working | `CascorServiceAdapter.get_decision_boundary()` transforms `grid_x`/`grid_y` → `xx`/`yy`/`Z` correctly |
| **Dataset metadata** display | ✅ Working | `ServiceBackend.get_dataset()` maps `train_samples` → `num_samples` correctly |
| **Training controls** (start/stop/pause/resume/reset) | ✅ Working | REST forwarding with proper error handling |
| **Parameter updates** (apply_params) | ✅ Working | `_CANOPY_TO_CASCOR_PARAM_MAP` correctly maps 6 of 7 canopy→cascor names |
| **WebSocket relay** (broadcasting to browser) | ✅ Working | Messages correctly relayed and broadcast (though with raw field names) |
| **Initial state sync** (status, phase, epoch, params) | ✅ Working | `CascorStateSync.sync()` handles both formats |
| **ResponseEnvelope unwrapping** | ✅ Working | All Phase 1 fixes correctly implemented |

---

## 20. Consolidated Fix Priority

| Priority | Root Cause | Effort | Risk | Impact |
|----------|-----------|--------|------|--------|
| **P0** | RC-1: Metrics format mismatch | Small (1-2 hrs) | Low | **Unblocks all metrics charts** |
| **P1** | RC-4: Topology format mismatch | Medium (2-3 hrs) | Medium | Enables topology visualization |
| **P2** | RC-5: Uppercase status in relay | Trivial (15 min) | None | Eliminates latent status misreporting |
| **P3** | RC-2: Relay callback field omission | Small (30 min) | Low | Improves `/api/state` accuracy |
| **P4** | RC-7: Hardcoded localhost URLs | Trivial (15 min) | None | Enables non-localhost deployment |
| **P5** | RC-6: State sync metrics normalization | Small (30 min) | Low | Eliminates latent format bug |
| **P6** | RC-9: Dead parameter mapping | Small (30 min) | Low | Fixes parameter display |
| **P7** | RC-10: Unmapped candidate_learning_rate | Trivial (15 min) | None | Enables candidate LR control |
| **P8** | RC-11: Double initialization | Trivial (15 min) | Low | Fixes fallback path |
| **P9** | RC-12: CasCor phase stuck | Small (30 min) | Low | Fixes phase labels (cascor-side) |
| **P10** | RC-13: Test coverage gap | Small (1 hr) | None | Prevents regression |
| **P11** | RC-8: Relay metric normalization | Small (30 min) | Low | Future-proofs WebSocket path |
| **P12** | RC-15: Canonical contract | Medium (2-3 hrs) | Moderate | Architectural improvement |
| — | RC-3: WebSocket consumption | Large | Moderate | Future enhancement |

---

## 21. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| RC-1 fix introduces regression in demo mode | Low | High | `_to_dashboard_metric()` only applies in service path; demo path unchanged |
| Falsy values (epoch=0, loss=0.0) treated as missing | Medium | Medium | `_first_defined()` + `"key" in dict` checks already in place |
| RC-4 topology transformation assumes specific weight ordering | Medium | Medium | Verify against cascor's actual serialization; add validation tests |
| Multiple concurrent fixes cause interaction bugs | Medium | Medium | Fix and test in priority order; each fix independently testable |
| FakeCascorClient divergence masks new issues | High | Medium | Add integration tests gated by `CASCOR_BACKEND_AVAILABLE=1` |
| RC-12 fix requires cascor release | Medium | Low | RC-12 is non-blocking; can ship canopy fixes independently |
| RC-1 fix breaks existing flat-format test assertions | High | Low | Update test expectations to nested format simultaneously |
| Demo mode regresses from shared code changes | Low | High | Demo already produces nested format; normalization is idempotent |

---

## 22. Verification Plan

### 22.1 Automated Tests

```bash
# Unit tests
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/unit/ -v

# Integration tests (mock-based)
pytest tests/integration/ -v -m "not requires_cascor"

# Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### 22.2 Manual Integration Test

```bash
# Terminal 1: Start juniper-data
cd /home/pcalnon/Development/python/Juniper/juniper-data
PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100

# Terminal 2: Start juniper-cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
JUNIPER_CASCOR_PORT=8201 python server.py

# Terminal 3: Start juniper-canopy (service mode)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 4: Verify API responses
# Metrics format (RC-1):
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, "phase": "...", ...}]}

# Topology format (RC-4):
curl -s http://localhost:8050/api/topology | python3 -m json.tool
# Expected: {"input_units": 2, "output_units": 2, "hidden_units": N,
#            "connections": [...], "nodes": [...]}

# Status (should already work):
curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 22.3 Visual Verification Checklist

- [ ] Loss chart displays live training data (not flat line at 0)
- [ ] Accuracy chart displays live accuracy curve
- [ ] Current loss display shows actual value (not "0.0000" or "--")
- [ ] Current accuracy display shows actual percentage (not "0.00%")
- [ ] Hidden units count shows actual count (not always 0)
- [ ] Hidden unit addition markers appear on plots when cascade events occur
- [ ] Network graph shows input/hidden/output nodes with connections (topology tab)
- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter shows actual epoch (including 0 at start)
- [ ] Phase indicator shows Output/Candidate transitions
- [ ] Parameter panel shows actual cascor parameters (not defaults)
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and shows correct state/metrics

---

## 23. Root Cause Dependency Graph

```
RC-15 (SYSTEMIC: No canonical backend contract)
  │
  ├── RC-1 (CRITICAL: Metrics flat vs nested mismatch)
  │     └── Direct cause of blank charts, zero displays
  │
  ├── RC-4 (MODERATE: Topology format mismatch)
  │     └── Network visualization always empty
  │
  ├── RC-6 (MODERATE: State sync raw metrics — latent)
  │     └── Wrong format if synced history ever used
  │
  ├── RC-8 (LOW: Relay broadcasts raw metrics — latent)
  │     └── Future blocker for WebSocket consumption
  │
  ├── RC-5 (MODERATE: Uppercase status — latent)
  │     └── Relay-driven state could show "Stopped" when running
  │
  ├── RC-2 (MODERATE: Relay callback omits fields)
  │     └── Stale epoch/hidden_units in relay-driven state
  │
  └── RC-3 (LOW: Dashboard ignores relay)
        └── Unused WebSocket data (performance issue only)

Independent issues:
  ├── RC-7 (LOW: Hardcoded localhost URLs)
  ├── RC-9 (LOW: Dead parameter mapping)
  ├── RC-10 (LOW: Unmapped candidate_learning_rate)
  ├── RC-11 (LOW: Double init on fallback)
  ├── RC-12 (LOW: CasCor phase stuck — cascor-side)
  └── RC-13 (LOW: Test coverage gap)
```

---

## 24. Files Requiring Modification (Summary)

### juniper-canopy

| File | Root Causes | Changes |
|------|-------------|---------|
| `src/backend/cascor_service_adapter.py` | RC-1, RC-2, RC-4, RC-5, RC-8, RC-9, RC-10 | Add `_to_dashboard_metric()` and apply in `_ServiceTrainingMonitor.get_recent_metrics()` and `get_current_metrics()`; expand relay callback; add `.lower()` before `_normalize_status()`; add `_transform_topology()`; fix param map |
| `src/backend/state_sync.py` | RC-6 | Normalize synced metrics history |
| `src/frontend/components/metrics_panel.py` | RC-7 | Replace 2 hardcoded localhost URLs |
| `src/main.py` | RC-11 | Guard double initialization on fallback path |
| `src/tests/unit/test_response_normalization.py` | RC-13 | Add nested format contract tests |

### juniper-cascor

| File | Root Causes | Changes |
|------|-------------|---------|
| `src/api/lifecycle/manager.py` | RC-12 | Update `monitor.current_phase` on phase transitions |

### Files NOT requiring modification

- `src/frontend/dashboard_manager.py` — callbacks are correct; data they receive is wrong
- `src/demo_mode.py` — demo format is the target format (working reference)
- `src/backend/demo_backend.py` — working reference implementation
- `juniper-cascor-client/` — no changes needed (Phase 1 FIX-SYS already done)

---

## Appendix A: Proposal Cross-Reference

| Proposal | Root Causes Identified | False Positives | Self-Corrections | Unique Contributions |
|----------|----------------------|-----------------|-------------------|---------------------|
| v1 | RC-1, RC-2, RC-3, RC-6 | RC-4 (params defaults) | Caught own RC-4 as false positive | Detailed evidence inventory; two-layer normalization analysis |
| v2 | RC-1, RC-2, RC-3, RC-4 (topology), RC-6, RC-9 | None | None needed | **Only proposal identifying topology format mismatch with full transformation code** |
| v3 | RC-1, RC-2, RC-3, RC-6 | RC-4 (params defaults) | Caught own RC-4 as false positive | Near-identical to v1 (same model/prompt variant) |
| v4 | RC-1, RC-2, RC-3, RC-4 (topology), RC-5 (uppercase), RC-7, RC-8, RC-9, RC-10, RC-14 | None | None needed | **Most comprehensive — identified 11 root causes including hardcoded URLs and dual normalization** |
| v5 | RC-1, RC-2, RC-3, RC-6, RC-12, RC-13 | RC-6 (fallback re-sync) | Retracted own RC-6 after validation | **Only proposal identifying cascor-side phase bug and test coverage gap** |
| v6 | RC-1, RC-2, RC-3, RC-6, RC-11, RC-15 | RC-5 (current metrics) | None needed | **Identified double-init bug and systemic contract issue** |
| v7 | RC-1, RC-2, RC-3, RC-5 (uppercase), RC-6, RC-8, RC-15 | None | None needed | **Best root cause dependency graph; clearly articulated systemic architectural gap** |

## Appendix B: Prior Analysis Documents

| Document | Location | Phase | Status |
|----------|----------|-------|--------|
| UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md | `juniper-canopy/notes/integration/` | Phase 1 | Fully implemented; fixes necessary but insufficient |
| ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md | `juniper-canopy/notes/integration/` | Phase 2 | RC-1/RC-2/RC-3 confirmed; scope was too narrow |
| PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v1-v7.md | `juniper-canopy/notes/integration/proposals/` | Phase 3 | 7 independent proposals — synthesized in this document |
| PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_cd8254d3-16bb-4212-b551-d9e911afd690.md | `juniper-canopy/notes/integration/` | Phase 4 | This document |
