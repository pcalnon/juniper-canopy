# Root Cause Analysis — Phase 3: External CasCor Display Failure

- **Version**: 1.0.0
- **Date**: 2026-03-27
- **Author**: Amp (AI Agent)
- **Status**: Analysis Complete — All Root Causes Identified
- **Related**:
  - `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` (Phase 1 — fixes implemented)
  - `ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md` (Phase 2 — partial analysis)

---

## 1. Executive Summary

Despite all Phase 1 fixes from the `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` being fully
implemented, and the Phase 2 analysis identifying 3 root causes, the juniper-canopy dashboard
still cannot display training data from an external juniper-cascor instance.

This Phase 3 analysis independently validates the Phase 2 findings and identifies **additional
root causes** that the Phase 2 analysis missed. The complete root cause inventory is:

| #        | Severity     | Root Cause                                                                       | Phase 2 Status |
|----------|--------------|----------------------------------------------------------------------------------|----------------|
| **RC-1** | **CRITICAL** | Metrics data format mismatch — service returns flat keys, dashboard reads nested | Identified ✓   |
| **RC-2** | MODERATE     | WebSocket relay state callback omits `current_epoch` and other fields            | Identified ✓   |
| **RC-3** | LOW          | Dashboard uses HTTP polling exclusively, ignoring WebSocket relay                | Identified ✓   |
| **RC-4** | MODERATE     | `_normalize_status()` fails for uppercase CasCor enum names on relay path        | **MISSED**     |
| **RC-5** | MODERATE     | Initial state sync bypasses adapter normalization — stores raw shapes            | **MISSED**     |
| **RC-6** | MODERATE     | Relay broadcasts raw CasCor payloads, not dashboard-compatible payloads          | **MISSED**     |
| **RC-7** | **SYSTEMIC** | No single canonical backend contract across demo and service modes               | **MISSED**     |

**Conclusion**: The Phase 2 analysis correctly identified the primary blocker (RC-1) but missed
4 additional issues that collectively represent a systemic architectural gap (RC-7). The
fundamental problem is that **service mode does not honor the same frontend data contract as
demo mode**, and this mismatch exists across multiple data paths, not just the metrics history path.

---

## 2. Methodology

### 2.1 Analysis Approach

1. **End-to-end data path tracing**: Traced every data path from cascor server → cascor-client
   → canopy backend → REST endpoint → dashboard callback → UI component
2. **Contract comparison**: Compared the data shapes produced by demo mode vs service mode
   at each layer boundary
3. **Cross-repository code inspection**: Examined the actual cascor server response format
   (field names, nesting, enum values) and compared against canopy's expectations
4. **Multi-agent validation**: Used independent analysis agents to validate findings and
   identify blind spots in the Phase 2 analysis

### 2.2 Repositories Examined

| Repository            | Key Files Examined                                                                                                                                                                                                        |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| juniper-cascor        | `api/lifecycle/manager.py`, `api/lifecycle/monitor.py`, `api/lifecycle/state_machine.py`, `api/routes/metrics.py`, `api/models/common.py`                                                                                 |
| juniper-canopy        | `backend/cascor_service_adapter.py`, `backend/service_backend.py`, `backend/state_sync.py`, `backend/demo_backend.py`, `demo_mode.py`, `main.py`, `frontend/dashboard_manager.py`, `frontend/components/metrics_panel.py` |
| juniper-cascor-client | `client.py`, `ws_client.py`                                                                                                                                                                                               |

---

## 3. Phase 2 Validation

### 3.1 RC-1: Metrics Data Format Mismatch — CONFIRMED as Primary Blocker

**Phase 2 assessment**: CRITICAL — Correctly identified.

**Independent verification**:

The complete data path in service mode:

```bash
cascor server (TrainingMonitor.on_epoch_end)
  → metric dict: {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase, timestamp}
  → wrapped in ResponseEnvelope: {"status": "success", "data": [...], "meta": {...}}

cascor-client (JuniperCascorClient.get_metrics_history)
  → returns raw response.json()

_ServiceTrainingMonitor.get_recent_metrics()
  → unwraps envelope to get list
  → calls _normalize_metric() on each entry
  → produces FLAT dict: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units, phase, timestamp}

ServiceBackend.get_metrics_history()
  → returns flat list unchanged

main.py /api/metrics/history
  → wraps in {"history": [flat_metrics_list]}

dashboard_manager._update_metrics_store_handler()
  → extracts payload["history"] → list of flat dicts

metrics_panel._update_metrics_display_handler()
  → reads: metric.get("metrics", {}).get("loss", 0) → ALWAYS 0
  → reads: metric.get("network_topology", {}).get("hidden_units", 0) → ALWAYS 0
```

**Contrast with demo mode** (working path):

```bash
demo_mode._emit_training_metrics()
  → produces NESTED dict:
    {
      "epoch": N,
      "metrics": {"loss": ..., "accuracy": ..., "val_loss": ..., "val_accuracy": ...},
      "network_topology": {"input_units": ..., "hidden_units": ..., "output_units": ...},
      "phase": ...,
      "timestamp": ...
    }

DemoBackend.get_metrics_history()
  → returns nested list unchanged

main.py /api/metrics/history
  → wraps in {"history": [nested_metrics_list]}

metrics_panel reads nested keys → WORKS
```

**Evidence — all 9 dashboard read sites affected**:

| File:Line                  | Code                                                                   | Expected Structure              | Service Value |
|----------------------------|------------------------------------------------------------------------|---------------------------------|---------------|
| `metrics_panel.py:1091`    | `m.get("network_topology", {}).get("hidden_units", 0)`                 | `network_topology.hidden_units` | Always 0      |
| `metrics_panel.py:1120`    | `latest.get("metrics", {}).get("loss", 0)`                             | `metrics.loss`                  | Always 0      |
| `metrics_panel.py:1121`    | `latest.get("metrics", {}).get("accuracy", 0)`                         | `metrics.accuracy`              | Always 0      |
| `metrics_panel.py:1122`    | `latest.get("network_topology", {}).get("hidden_units", 0)`            | `network_topology.hidden_units` | Always 0      |
| `metrics_panel.py:1330`    | `metric.get("metrics", {}).get("loss", 0)`                             | `metrics.loss`                  | Always 0      |
| `metrics_panel.py:1449`    | `metrics_data[i-1].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | Always 0      |
| `metrics_panel.py:1450`    | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)`   | `network_topology.hidden_units` | Always 0      |
| `metrics_panel.py:1499`    | `metric.get("metrics", {}).get("accuracy", 0)`                         | `metrics.accuracy`              | Always 0      |
| `metrics_panel.py:1561-62` | `metrics_data[i-1].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | Always 0      |

**Why the Phase 1 plan missed this**: The `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` defined
a "Canonical Internal Contract" (Section 6.2) using **flat** keys (`train_loss`, `train_accuracy`,
`hidden_units`). This contract was designed to normalize cascor's raw response format but was
never validated against the dashboard's actual input format, which uses **nested** keys
(`metrics.loss`, `network_topology.hidden_units`). The plan focused on the normalization
boundary but stopped before the last mile.

### 3.2 RC-2: WebSocket Relay State Callback Omits Fields — CONFIRMED

**Phase 2 assessment**: MODERATE — Correctly identified.

**Independent verification** at `cascor_service_adapter.py:222-223`:

```python
status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
self._state_update_callback(status=status, phase=data.get("phase", ""))
```

Only `status` and `phase` are forwarded. CasCor WebSocket `state` messages include
`current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, and `max_epochs` — all
of which are discarded.

**Impact**: The `/api/state` endpoint reads from `training_state.get_state()` (main.py:586),
which only receives `status` and `phase` updates via the relay callback. After initial sync,
`current_epoch` becomes stale. However, `/api/status` makes a fresh REST call on each poll,
so the status bar is not affected.

### 3.3 RC-3: Dashboard Ignores WebSocket Relay — CONFIRMED

**Phase 2 assessment**: LOW — Correctly identified.

**Independent verification**: The dashboard uses `dcc.Interval` callbacks for all data fetching:

- `fast-update-interval` (1000ms): status bar, metrics store
- `slow-update-interval` (5000ms): topology, dataset, decision boundary

No Dash callback reads from the `websocket-data` div (defined at dashboard_manager.py:876).
This is a performance/UX issue, not a functional blocker.

---

## 4. Newly Identified Root Causes

### 4.1 RC-4: `_normalize_status()` Fails for Uppercase CasCor Enum Names

**Severity**: MODERATE
**Phase 2 status**: MISSED

#### The Problem

CasCor's `TrainingStateMachine.get_state_summary()` returns status as Python enum `.name`
values, which are **UPPERCASE**: `"STARTED"`, `"PAUSED"`, `"COMPLETED"`, `"FAILED"`, `"STOPPED"`.

The `_normalize_status()` mapping in `state_sync.py:137-153` has entries for lowercase and
title case, but **not uppercase**:

```python
mapping = {
    "idle": "Stopped",
    "training": "Started",
    "started": "Started",     # lowercase only
    "paused": "Paused",       # lowercase only
    "complete": "Completed",
    "completed": "Completed", # lowercase only
    "failed": "Failed",       # lowercase only
    "stopped": "Stopped",     # lowercase only
    "running": "Started",
    # Already-normalized values
    "Stopped": "Stopped",
    "Started": "Started",
    "Paused": "Paused",
    "Completed": "Completed",
    "Failed": "Failed",
}
```

#### Where This Matters

- **Initial sync path** (`CascorStateSync.sync()`): The status is lowered to lowercase before
  lookup at line 70 (`sm.get("status", "").lower()`), so this path is **partially protected**.
  However, the lowering is embedded in a complex `or`-chain expression that may not always
  reach the `.lower()` call depending on which dict keys are present.

- **Relay callback path** (`cascor_service_adapter.py:222`):

  ```python
  status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
  ```

  There is **no `.lower()` call** before `_normalize_status()`. If CasCor sends `"STARTED"`,
  this returns `"Stopped"` (the default fallback).

#### Consequence

- Relay-driven state updates can incorrectly set status to `"Stopped"` when training is actually
  running
- The `/api/state` endpoint may show incorrect status if it reads relay-updated state
- The status bar is **not affected** because it reads from `/api/status`, which makes a fresh
  REST call

#### Evidence

CasCor state machine at `juniper-cascor/src/api/lifecycle/state_machine.py:215-216`:

```python
def get_state_summary(self) -> dict:
    return {
        "status": self._status.name,   # e.g. "STARTED", "PAUSED"
        "phase": self._phase.name,     # e.g. "OUTPUT", "CANDIDATE"
        ...
    }
```

### 4.2 RC-5: Initial State Sync Bypasses Adapter Normalization

**Severity**: MODERATE
**Phase 2 status**: MISSED

#### The Problem, RC-5

`ServiceBackend.initialize()` creates the state sync with the **raw client**, bypassing
the adapter's normalization layer:

```python
# service_backend.py:189
self._synced_state = CascorStateSync(self._adapter._client).sync()
```

`CascorStateSync.sync()` directly calls client methods (`get_training_status()`,
`get_training_params()`, `get_metrics_history()`, `get_topology()`) and stores their
responses with minimal transformation:

1. **Metrics history** (`state_sync.py:117-128`): Stored as raw cascor format — `loss`,
   `accuracy`, `validation_loss`, `validation_accuracy` field names, no nested structure.
   Not passed through `_normalize_metric()` or converted to dashboard format.

2. **Training params** (`state_sync.py:98-103`): Stored using raw CasCor parameter names
   (`learning_rate`, `max_hidden_units`, `epochs_max`), not mapped to Canopy `nn_*/cn_*`
   namespace via `_CASCOR_TO_CANOPY_PARAM_MAP`.

3. **Training status**: Partially normalized via `_normalize_status()` but with the
   uppercase bug (RC-4).

#### Consequence, RC-5

- The synced state snapshot contains data in a format different from what the dashboard expects
- Any code that uses `get_synced_state()` to seed initial data will have format mismatches
- The sync path and the polling path produce different data shapes for the same information

### 4.3 RC-6: Relay Broadcasts Raw CasCor Payloads

**Severity**: MODERATE
**Phase 2 status**: MISSED (partially noted in RC-3 but not explicitly called out)

#### The Problem, RC-6

The metrics relay at `cascor_service_adapter.py:206` broadcasts raw CasCor messages:

```python
await websocket_manager.broadcast({"type": msg_type, "data": data})
```

This `data` is the raw CasCor WebSocket message payload — it uses CasCor's field names, enum
cases, and nesting structure. No normalization is applied before broadcast.

#### Consequence, RC-6

- Even if RC-3 were fixed (dashboard consuming WebSocket), the data would still be in the
  wrong format
- Metrics messages would use `loss`/`accuracy` field names (not nested `metrics.loss`)
- Status messages would use uppercase enum values like `"STARTED"` and `"OUTPUT"`
- This is a **future blocker** — fixing RC-3 alone would not enable real-time WebSocket updates

### 4.4 RC-7: No Single Canonical Backend Contract (Systemic Root Cause)

**Severity**: SYSTEMIC
**Phase 2 status**: MISSED

#### The Problem, RC-7

This is the deepest root cause. The system has **mode-dependent data schemas** — different
data paths produce different shapes for the same information:

| Data Path                    | Data Shape               | Matches Dashboard? |
|------------------------------|--------------------------|--------------------|
| Demo mode metrics history    | Nested (`metrics.loss`)  | ✅ Yes             |
| Service mode metrics history | Flat (`train_loss`)      | ❌ No              |
| Service mode status          | Flat (`is_running`)      | ✅ Yes             |
| Service mode state sync      | Raw CasCor format        | ❌ No              |
| Service mode relay broadcast | Raw CasCor format        | ❌ No              |
| Demo mode status             | Flat (`is_running`)      | ✅ Yes             |

The Phase 1 plan correctly identified that normalization should happen at a single boundary
(`CascorServiceAdapter`), but the implementation normalized to a **different contract** than
what the dashboard expects. The plan defined its own "Canonical Internal Contract" (Section 6.2)
without validating it against the dashboard's actual input format.

#### Why This Matters

- Partial fixes don't solve the problem — each data path has independent schema issues
- Testing against one path (e.g., `/api/status`) can pass while others fail
- The root cause persists because the system lacks a single source of truth for the
  dashboard-facing data contract

---

## 5. Root Cause Dependency Graph

```bash
RC-7 (Systemic: No canonical backend contract)
  │
  ├── RC-1 (CRITICAL: Metrics flat vs nested mismatch)
  │     └── Direct cause of blank charts, zero displays
  │
  ├── RC-5 (MODERATE: State sync bypasses normalization)
  │     └── Initial state uses wrong data shapes
  │
  ├── RC-6 (MODERATE: Relay broadcasts raw payloads)
  │     └── Future blocker for WebSocket consumption
  │
  ├── RC-4 (MODERATE: Uppercase status normalization failure)
  │     └── Relay-driven state shows "Stopped" when running
  │
  ├── RC-2 (MODERATE: Relay callback omits fields)
  │     └── Stale epoch/hidden_units in relay-driven state
  │
  └── RC-3 (LOW: Dashboard ignores relay)
        └── Unused WebSocket data (performance issue only)
```

---

## 6. Impact Assessment

### 6.1 What Is Broken (Visible to User)

| Dashboard Element            | Expected       | Actual           | Caused By |
|------------------------------|----------------|------------------|-----------|
| Loss chart                   | Training curve | Flat line at 0   | RC-1      |
| Accuracy chart               | Accuracy curve | Flat line at 0   | RC-1      |
| Current loss display         | e.g. "0.0234"  | "0.0000" or "--" | RC-1      |
| Current accuracy display     | e.g. "94.50%"  | "0.00%" or "--"  | RC-1      |
| Hidden units count (metrics) | Actual count   | Always 0         | RC-1      |
| Hidden unit addition markers | Vertical lines | Never rendered   | RC-1      |

### 6.2 What Works Correctly

| Dashboard Element | Status  | Why It Works                                                 |
|-------------------|---------|--------------------------------------------------------------|
| Status bar status | ✅      | `ServiceBackend.get_status()` produces flat keys that match  |
| Status bar epoch  | ✅      | Fresh REST call via `/api/status` on each poll               |
| Status bar phase  | ✅      | Phase lowered correctly in `get_status()`                    |
| Status bar hidden | ✅      | `_first_defined()` correctly extracts from nested            |
| Connection status | ✅      | Uses `is_alive()` health check                               |

### 6.3 What May Be Subtly Wrong

| Element                             | Risk   | Caused By |
|-------------------------------------|--------|-----------|
| Relay-driven status shows "Stopped" | Medium | RC-4      |
| `/api/state` epoch becomes stale    | Medium | RC-2      |
| Initial state has wrong format      | Medium | RC-5      |
| Params may show raw CasCor names    | Low    | RC-5      |

---

## 7. Evaluation of Phase 2 Analysis

### 7.1 Accuracy Assessment

| Criterion                 | Assessment                                                         |
|---------------------------|--------------------------------------------------------------------|
| RC-1 identification       | ✅ Correct and well-evidenced                                      |
| RC-2 identification       | ✅ Correct, properly scoped as secondary                           |
| RC-3 identification       | ✅ Correct, properly scoped as low priority                        |
| Fix recommendation (RC-1) | ✅ Option A (normalize at service backend) is sound                |
| Fix recommendation (RC-2) | ✅ Forward additional fields — correct approach                    |
| Fix recommendation (RC-3) | ✅ Correctly deferred as non-blocker                               |
| Completeness              | ⚠️ Missed 4 additional root causes (RC-4 through RC-7)             |
| Systemic analysis         | ⚠️ Identified RC-1 correctly but didn't trace the systemic pattern |

### 7.2 What Phase 2 Got Right

1. **Correctly identified RC-1 as the primary blocker** — the flat-vs-nested mismatch is
   indeed the direct cause of blank charts
2. **Provided clear evidence** with exact line numbers and code snippets
3. **Verified all Phase 1 fixes as implemented** — confirmed the prior plan's work was done
4. **Identified why the status bar works** — correctly traced the separate status data path
5. **Recommended the right fix approach** — Option A (normalize at service backend level)
   is the correct strategy

### 7.3 What Phase 2 Missed

1. **The uppercase `_normalize_status()` bug** (RC-4) on the relay path — a real functional
   bug that causes status misreporting
2. **The state sync format gap** (RC-5) — the sync path stores raw data, not dashboard-
   compatible data
3. **The relay payload format gap** (RC-6) — even if the dashboard consumed WebSocket data,
   it would still be in the wrong format
4. **The systemic contract gap** (RC-7) — the deeper pattern that all these issues share:
   service mode doesn't honor the demo mode data contract

---

## 8. Fix Recommendations

### 8.1 Priority 1 — Fix RC-1 (Resolves Visible Failure)

**Approach**: Add a `_to_dashboard_metric()` transformation after `_normalize_metric()` that
restructures flat keys into the nested format the dashboard expects.

**Location**: `cascor_service_adapter.py` or `service_backend.py`

```python
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

**Apply to**: `_ServiceTrainingMonitor.get_recent_metrics()` and `get_current_metrics()`.

### 8.2 Priority 2 — Fix RC-4 (Resolves Status Misreporting)

**Approach**: Case-normalize the input before lookup in `_normalize_status()`.

```python
@staticmethod
def _normalize_status(raw: str) -> str:
    """Map cascor state strings to canopy display strings."""
    lookup = raw.lower() if isinstance(raw, str) else ""
    mapping = {
        "idle": "Stopped",
        "training": "Started",
        "started": "Started",
        "paused": "Paused",
        "complete": "Completed",
        "completed": "Completed",
        "failed": "Failed",
        "stopped": "Stopped",
        "running": "Started",
    }
    return mapping.get(lookup, "Stopped")
```

### 8.3 Priority 3 — Fix RC-2 (Forward Additional Relay Fields)

**Approach**: Extend the relay callback to forward `current_epoch`, `hidden_units`, and
other fields from CasCor state messages.

### 8.4 Priority 4 — Fix RC-5 (Normalize State Sync Output)

**Approach**: Apply `_normalize_metric()` + `_to_dashboard_metric()` to the metrics history
stored in `SyncedState`, and map params through `_CASCOR_TO_CANOPY_PARAM_MAP`.

### 8.5 Priority 5 — Fix RC-6 (Normalize Relay Broadcasts)

**Approach**: Apply the same metric normalization to relay `metrics` type messages before
broadcasting. This is a future concern — only needed if/when the dashboard starts consuming
WebSocket data (RC-3).

### 8.6 Long-term — Address RC-7 (Establish Canonical Contract)

**Approach**: Define a single typed frontend DTO layer and enforce it across all backend paths.
Add contract tests comparing demo and service payload shapes for `/api/status`,
`/api/metrics/history`, and `/api/state`.

---

## 9. Risk Assessment

| Risk                                                    | Impact                      | Probability | Mitigation                                                                 |
|---------------------------------------------------------|-----------------------------|-------------|----------------------------------------------------------------------------|
| RC-1 fix introduces regression in demo mode             | Charts break in demo mode   | Low         | `_to_dashboard_metric()` only applies to service path; demo path unchanged |
| Falsy values (epoch=0, loss=0.0) treated as missing     | Charts show gaps            | Medium      | Use `_first_defined()` and `"key" in dict` checks (already in place)       |
| RC-4 fix causes normalization of unknown status strings | Silent default to "Stopped" | Low         | Existing default behavior preserved; `.lower()` only added to input        |
| Multiple concurrent fixes cause interaction bugs        | Unexpected behavior         | Medium      | Fix in priority order; test each fix independently before combining        |
| State sync format change breaks downstream consumers    | Other code reads raw shapes | Low         | Verify no code depends on raw SyncedState.metrics_history format           |

---

## 10. Verification Plan

### 10.1 Automated Tests

```bash
# After applying fixes:
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython

# Unit tests
pytest tests/unit/ -v

# Integration tests (mock-based)
pytest tests/integration/ -v -m "not requires_cascor"

# Full suite
pytest tests/ --cov=. --cov-report=term-missing
```

### 10.2 Contract Tests (Recommended — New)

Add tests comparing demo and service output shapes:

```python
def test_metrics_history_contract_matches_demo():
    """Service mode metrics must use same nested format as demo mode."""
    demo_metric = demo_backend.get_metrics_history(1)[0]
    service_metric = service_backend.get_metrics_history(1)[0]
    assert "metrics" in service_metric, "Service metric missing nested 'metrics' key"
    assert "network_topology" in service_metric, "Service metric missing nested 'network_topology' key"
    assert set(demo_metric.keys()) == set(service_metric.keys())
```

### 10.3 Manual Verification

```bash
# Start services
# Terminal 1: cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src && python server.py

# Terminal 2: canopy (service mode)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: verify
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Should show: {"history": [{"epoch": ..., "metrics": {"loss": ...}, "network_topology": {"hidden_units": ...}}, ...]}

curl -s http://localhost:8050/api/status | python3 -m json.tool
# Should show: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 10.4 Visual Verification Checklist

- [ ] Loss chart shows training loss curve (not flat line at 0)
- [ ] Accuracy chart shows accuracy curve
- [ ] Current loss display shows actual loss value (e.g., "0.0234")
- [ ] Current accuracy display shows actual accuracy (e.g., "94.50%")
- [ ] Hidden units count updates on cascade events
- [ ] Hidden unit addition markers render as vertical lines
- [ ] Status bar shows correct Running/Paused/Stopped state
- [ ] Epoch counter increments during training
- [ ] Phase indicator shows Output/Candidate transitions

---

## 11. Appendix: Complete Data Path Reference

### 11.1 Service Mode — Metrics History (Broken)

```bash
cascor server
  TrainingMonitor.on_epoch_end()
    → {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase, timestamp}
  TrainingLifecycleManager.get_metrics_history()
    → returns list from TrainingMonitor.get_recent_metrics()
  success_response()
    → {"status": "success", "data": [...], "meta": {...}}

cascor-client
  JuniperCascorClient.get_metrics_history()
    → HTTP GET /v1/metrics/history
    → returns raw response.json() (full ResponseEnvelope)

canopy backend
  _ServiceTrainingMonitor.get_recent_metrics()
    → unwraps envelope → gets list
    → _normalize_metric() on each entry
    → FLAT: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units}
  ServiceBackend.get_metrics_history()
    → returns flat list unchanged

canopy main.py
  /api/metrics/history endpoint
    → {"history": [flat_list]}

canopy dashboard
  _update_metrics_store_handler()
    → extracts payload["history"]
  metrics_panel reads:
    metric.get("metrics", {}).get("loss", 0) → 0 (BROKEN)
    metric.get("network_topology", {}).get("hidden_units", 0) → 0 (BROKEN)
```

### 11.2 Demo Mode — Metrics History (Working)

```bash
demo_mode._emit_training_metrics()
  → NESTED: {epoch, metrics: {loss, accuracy, ...}, network_topology: {hidden_units, ...}, phase, timestamp}
  → appended to self.metrics_history

DemoBackend.get_metrics_history()
  → returns nested list

main.py /api/metrics/history
  → {"history": [nested_list]}

dashboard reads:
  metric.get("metrics", {}).get("loss", 0) → actual loss value (WORKS)
```

### 11.3 Service Mode — Status Bar (Working)

```bash
ServiceBackend.get_status()
  → calls adapter.get_training_status() (REST to cascor)
  → unwraps envelope
  → detects nested structure
  → transforms to flat: {is_running, is_paused, phase, current_epoch, hidden_units}

dashboard_manager._build_unified_status_bar_content()
  → reads flat keys: is_running, is_paused, current_epoch, hidden_units
  → WORKS (flat keys match)
```

---

## 12. Appendix: File Reference

| File                                       | Repository     | Role                                    |
|--------------------------------------------|----------------|-----------------------------------------|
| `src/api/lifecycle/manager.py`             | juniper-cascor | Training lifecycle, metrics collection  |
| `src/api/lifecycle/monitor.py`             | juniper-cascor | TrainingMonitor — metric record format  |
| `src/api/lifecycle/state_machine.py`       | juniper-cascor | State machine — UPPERCASE enum names    |
| `src/api/models/common.py`                 | juniper-cascor | ResponseEnvelope wrapper                |
| `src/api/routes/metrics.py`                | juniper-cascor | /v1/metrics/history endpoint            |
| `src/backend/cascor_service_adapter.py`    | juniper-canopy | Normalization boundary (partial)        |
| `src/backend/service_backend.py`           | juniper-canopy | BackendProtocol for service mode        |
| `src/backend/state_sync.py`                | juniper-canopy | Initial state sync on connect           |
| `src/backend/demo_backend.py`              | juniper-canopy | BackendProtocol for demo mode           |
| `src/demo_mode.py`                         | juniper-canopy | Demo training — produces nested metrics |
| `src/main.py`                              | juniper-canopy | REST endpoints, backend routing         |
| `src/frontend/dashboard_manager.py`        | juniper-canopy | Dash app, polling, metrics store        |
| `src/frontend/components/metrics_panel.py` | juniper-canopy | Charts — reads nested keys              |
