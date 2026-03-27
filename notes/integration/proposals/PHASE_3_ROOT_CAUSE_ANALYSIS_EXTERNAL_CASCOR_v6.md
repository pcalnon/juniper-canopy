# Root Cause Analysis — Phase 3: External CasCor Dashboard Display Failure

- **Version**: 1.0.0
- **Date**: 2026-03-27
- **Author**: Amp (AI Agent)
- **Status**: Analysis Complete — Root Causes Identified and Validated
- **Related**:
  - `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` (Phase 1 — implemented)
  - `ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md` (Phase 2 — analysis only)

---

## 1. Executive Summary

Despite all Phase 1 fixes from the `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` being fully
implemented and verified in the codebase, the juniper-canopy dashboard still fails to display
training metrics when connected to an external juniper-cascor instance. A Phase 2 analysis
identified three root causes (RC-1 through RC-3). This Phase 3 investigation independently
validates those findings, corrects one inaccuracy, identifies additional root causes missed by
both prior phases, and provides a unified picture of all remaining blockers.

### Summary of Findings

| #        | Severity     | Root Cause                                                                            | Phase 2 Status       |
|----------|--------------|---------------------------------------------------------------------------------------|----------------------|
| **RC-1** | **CRITICAL** | Metrics format mismatch: service backend emits flat keys; dashboard reads nested keys | Correctly identified |
| **RC-2** | MODERATE     | WebSocket relay state callback omits `current_epoch` and other fields                 | Correctly identified |
| **RC-3** | LOW          | Dashboard uses HTTP polling exclusively, ignoring WebSocket relay                     | Correctly identified |
| **RC-4** | **MODERATE** | State sync `metrics_history` stores raw/unnormalized cascor metrics                   | **Not identified**   |
| **RC-5** | **MODERATE** | `/api/metrics` (current snapshot) returns flat format incompatible with dashboard     | **Not identified**   |
| **RC-6** | LOW          | Double initialization on fallback-to-demo path in `main.py`                           | **Not identified**   |
| **RC-7** | **SYSTEMIC** | No single canonical metric contract enforced across all ingress paths                 | **Not identified**   |

**Primary blocker**: RC-1 is the sole CRITICAL root cause preventing metrics display. RC-4,
RC-5, and RC-7 are secondary issues that would cause failures or inconsistencies even after
RC-1 is fixed, depending on which data paths are exercised.

---

## 2. Methodology

### 2.1 Analysis Approach

This analysis was conducted by:

1. Reading all Phase 1 and Phase 2 documentation
2. Tracing every data path from the cascor server through the client library, service adapter,
   backend, REST API, and into the dashboard frontend components
3. Comparing the actual data structures produced at each layer against what the consuming layer
   expects
4. Cross-validating findings with an independent AI review (oracle)
5. Confirming all code references against the current HEAD of each repository

### 2.2 Repositories Examined

| Repository            | Purpose in Data Flow                                    |
|-----------------------|---------------------------------------------------------|
| juniper-cascor        | Server: produces ResponseEnvelope-wrapped API responses |
| juniper-cascor-client | HTTP client: returns raw ResponseEnvelope JSON          |
| juniper-canopy        | Dashboard: adapter, backend, REST API, frontend         |

### 2.3 Data Flow Traced

Five complete data paths were traced end-to-end:

1. **Metrics history polling** (dashboard → `/api/metrics/history` → backend → adapter → client → cascor)
2. **Current metrics polling** (dashboard → `/api/metrics` → backend → adapter → client → cascor)
3. **Status bar polling** (dashboard → `/api/status` → backend → adapter → client → cascor)
4. **State sync on connect** (backend initialize → state_sync → client → cascor)
5. **WebSocket relay** (cascor WS → adapter relay → websocket_manager → browser)

---

## 3. Phase 1 Fix Verification

All 14 fixes from the `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` were verified as
**fully implemented** in the current codebase. The implementation is correct for its stated
goals. The problem is that the stated goals were insufficient — they normalized cascor's
ResponseEnvelope format into a flat "canonical" format that does not match what the dashboard
frontend actually reads.

| FIX ID  | File                                | Status     | Verified At                                        |
|---------|-------------------------------------|------------|----------------------------------------------------|
| FIX-1   | `cascor_service_adapter.py:96-108`  | ✅ Correct | `get_recent_metrics()` dual-path envelope handling |
| FIX-2   | `cascor_service_adapter.py:72-84`   | ✅ Correct | `is_training` with `is not None` guard             |
| FIX-3   | `cascor_service_adapter.py:86-94`   | ✅ Correct | `get_current_metrics()` unwraps envelope           |
| FIX-4   | `service_backend.py:100-136`        | ✅ Correct | `get_status()` flat dict builder                   |
| FIX-5   | `state_sync.py:59-92`               | ✅ Correct | `sync()` handles nested status                     |
| FIX-6   | `state_sync.py:117-127`             | ✅ Correct | Metrics history handles both formats               |
| FIX-7   | `state_sync.py:98-103`              | ✅ Correct | Params handles flat and nested                     |
| FIX-8   | `cascor_service_adapter.py:310-321` | ✅ Correct | `is_training_in_progress()`                        |
| FIX-9   | `cascor_service_adapter.py:367`     | ✅ Correct | Reverse param map auto-generated                   |
| FIX-10  | `cascor_service_adapter.py:386-402` | ✅ Correct | `get_canopy_params()` dual-path                    |
| FIX-11  | `service_backend.py:155-168`        | ✅ Correct | Dataset response key mapping                       |
| FIX-12  | `state_sync.py:137-154`             | ✅ Correct | Status normalization expanded                      |
| FIX-13  | `cascor_service_adapter.py:430-460` | ✅ Correct | `_normalize_metric()` field mapping                |
| FIX-SYS | `fake_client.py` (cascor-client)    | ✅ Correct | FakeCascorClient ResponseEnvelope format           |

---

## 4. Root Cause #1: Metrics Format Mismatch (CRITICAL)

### 4.1 Phase 2 Assessment: CONFIRMED CORRECT

The Phase 2 analysis correctly identified this as the primary root cause.

### 4.2 Detailed Evidence

#### What the Dashboard Reads (Nested Format)

The `MetricsPanel` component (`frontend/components/metrics_panel.py`) reads metrics using
**nested dictionary access** at 12+ locations:

| Location (line) | Code                                                                 | Expected Key Path               |
|-----------------|----------------------------------------------------------------------|---------------------------------|
| 1091            | `m.get("network_topology", {}).get("hidden_units", 0)`               | `network_topology.hidden_units` |
| 1120            | `latest.get("metrics", {}).get("loss", 0)`                           | `metrics.loss`                  |
| 1121            | `latest.get("metrics", {}).get("accuracy", 0)`                       | `metrics.accuracy`              |
| 1122            | `latest.get("network_topology", {}).get("hidden_units", 0)`          | `network_topology.hidden_units` |
| 1330            | `metric.get("metrics", {}).get("loss", 0)`                           | `metrics.loss`                  |
| 1449-1450       | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` |
| 1499            | `metric.get("metrics", {}).get("accuracy", 0)`                       | `metrics.accuracy`              |
| 1561-1562       | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` |

#### What Demo Mode Produces (Works — Nested Format)

`demo_mode.py:1162-1177` produces metrics in the nested format:

```python
metrics = {
    "epoch": self.current_epoch,
    "metrics": {                              # ← NESTED dict
        "loss": float(loss),
        "accuracy": float(accuracy),
        "val_loss": float(val_loss),
        "val_accuracy": float(val_accuracy),
    },
    "network_topology": {                     # ← NESTED dict
        "input_units": self.network.input_size,
        "hidden_units": len(self.network.hidden_units),
        "output_units": self.network.output_size,
    },
    "phase": phase_name,
    "timestamp": datetime.now().isoformat(),
}
```

#### What Service Mode Produces (Broken — Flat Format)

`cascor_service_adapter.py:431-460` `_normalize_metric()` produces flat keys:

```python
return {
    "epoch": entry.get("epoch", 0),
    "train_loss": ...,           # ← FLAT (dashboard reads metrics.loss)
    "train_accuracy": ...,       # ← FLAT (dashboard reads metrics.accuracy)
    "val_loss": ...,             # ← FLAT
    "val_accuracy": ...,         # ← FLAT
    "hidden_units": ...,         # ← FLAT (dashboard reads network_topology.hidden_units)
    "phase": ...,
    "timestamp": ...,
}
```

#### Complete Data Flow (Service Mode — `/api/metrics/history`)

```bash
1. Dashboard interval fires (1000ms)
2. dashboard_manager.py:1690 → GET /api/metrics/history?limit=N
3. main.py:640-650 → return {"history": backend.get_metrics_history(count)}
4. service_backend.py:141-142 → self._adapter.training_monitor.get_recent_metrics(count)
5. cascor_service_adapter.py:96-108 → client.get_metrics_history(count)
6. juniper_cascor_client/client.py:202-211 → GET /v1/metrics/history → returns RAW ResponseEnvelope
7. cascor_service_adapter.py:102 → [_normalize_metric(m) for m in data]  → FLAT keys
8. dashboard_manager.py:1694-1701 → extracts list from {"history": [...]}
9. metrics_panel.py:1120 → latest.get("metrics", {}).get("loss", 0) → returns 0 (ALWAYS)
10. metrics_panel.py:1122 → latest.get("network_topology", {}).get("hidden_units", 0) → returns 0 (ALWAYS)
```

### 4.3 Consequence

- **Loss/accuracy plots**: All y-values are `0` → flat line at zero or empty
- **Current loss/accuracy displays**: Show "0.0000" / "0.00%"
- **Hidden units count**: Always shows `0`
- **Hidden unit markers on plots**: Never rendered (prev and curr always equal 0)

### 4.4 Root Cause of the Root Cause

The Phase 1 `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` defined a "Canonical Internal
Contract" (Section 6.2) using **flat** keys. This contract was designed to normalize cascor's
ResponseEnvelope but was never validated against the dashboard's **actual input contract**
(the nested format that demo mode produces). The plan focused on the unwrapping boundary but
stopped before the last mile — where normalized data meets the dashboard callbacks.

---

## 5. Root Cause #2: WebSocket Relay State Callback Omits Fields (MODERATE)

### 5.1 Phase 2 Assessment: CONFIRMED CORRECT

### 5.2 Evidence

At `cascor_service_adapter.py:218-225`:

```python
if msg_type == "state" and self._state_update_callback and isinstance(data, dict):
    status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
    self._state_update_callback(status=status, phase=data.get("phase", ""))
    # ^^^ Only status and phase — no current_epoch, hidden_units, etc.
```

The cascor server's WebSocket `state` messages contain `current_epoch`, `current_step`,
`learning_rate`, `max_hidden_units`, and `max_epochs` — all discarded.

### 5.3 Impact

- `/api/state` endpoint reads from `training_state.get_state()` (main.py:586), which only
  receives `status` and `phase` via the relay callback
- After initial sync (main.py:192-199), `current_epoch` in `training_state` becomes stale
- **Mitigated** by: the status bar reads from `/api/status` which makes a fresh REST call

---

## 6. Root Cause #3: Dashboard Ignores WebSocket Relay (LOW)

### 6.1 Phase 2 Assessment: CONFIRMED CORRECT

### 6.2 Evidence

Dashboard polls via `dcc.Interval` callbacks at 1000ms and 5000ms intervals using HTTP GET
requests. A `websocket-data` div exists in the layout (dashboard_manager.py:876) but **no Dash
callback reads from it**. WebSocket messages are broadcast to browser clients but never consumed
by Dash callbacks.

### 6.3 Impact

Latency only — HTTP polling at 1s intervals is adequate for training progress display. Not
a functional blocker.

---

## 7. Root Cause #4: State Sync Metrics History Not Normalized (MODERATE) — NEW

### 7.1 Discovery

**Not identified by Phase 2 analysis.**

### 7.2 Evidence

In `state_sync.py:115-129`, the `sync()` method stores raw cascor metrics history directly
without passing through any normalization:

```python
# state_sync.py:115-129
history_response = self._client.get_metrics_history(count=metrics_limit)
if isinstance(history_response, dict):
    data = history_response.get("data", history_response)
    if isinstance(data, list):
        state.metrics_history = data        # ← RAW cascor format stored directly
    elif isinstance(data, dict):
        state.metrics_history = data.get("history", [])  # ← Also raw
```

The raw cascor metrics use flat keys (`loss`, `accuracy`, `validation_loss`,
`validation_accuracy`, `hidden_units`) — no `metrics` or `network_topology` nesting.

There is **no call** to `CascorServiceAdapter._normalize_metric()` or any nested-format
transformation on this path.

### 7.3 Current Impact

In the current code (`main.py:189-202`), `synced.metrics_history` is **not directly
propagated** to the dashboard. Only `status`, `phase`, `current_epoch`, `max_epochs`, and
some params are extracted from the synced state. So this is currently a **latent bug**.

### 7.4 Future Impact

If any code path were added to display the synced metrics history (e.g., pre-populating
charts on connect before the first poll), the data would be in the wrong format. This should
be fixed alongside RC-1 to ensure all metric data passes through a single normalization point.

### 7.5 Severity Rationale

Rated MODERATE because:

- It is a real consistency bug with incorrect data in a stored data structure
- It is latent today but represents a trap for future development
- Fixing it is trivial once RC-1's normalization is implemented

---

## 8. Root Cause #5: `/api/metrics` Current Snapshot Also Flat (MODERATE) — NEW

### 8.1 Discovery

**Not identified by Phase 2 analysis**, which focused only on `/api/metrics/history`.

### 8.2 Evidence

The `/api/metrics` endpoint (current snapshot) follows the same broken path:

```bash
main.py:630-637 → return backend.get_metrics()
service_backend.py:138-139 → self._adapter.training_monitor.get_current_metrics()
cascor_service_adapter.py:86-94 → unwraps envelope, calls _normalize_metric()
→ Returns flat format
```

`_ServiceTrainingMonitor.get_current_metrics()` at line 86-94:

```python
def get_current_metrics(self) -> Dict[str, Any]:
    result = self._client.get_metrics()
    if isinstance(result, dict) and "data" in result:
        data = result["data"]
        return CascorServiceAdapter._normalize_metric(data) if isinstance(data, dict) else result
    return result if isinstance(result, dict) else {}
```

This passes through `_normalize_metric()` which produces **flat** keys — the same mismatch
as RC-1 but on the current-metrics path.

### 8.3 Impact

Any dashboard component reading current metrics using nested access patterns will get default
values. Currently the dashboard primarily uses the history endpoint for chart data, but the
current metrics display values (loss_str, accuracy_str at lines 1120-1121 of metrics_panel.py)
also come from the history data's last entry.

### 8.4 Severity Rationale

MODERATE because it is the same class of bug as RC-1 on a different path. Fixing RC-1's
normalization function to produce nested format automatically fixes this too if the same
function is used.

---

## 9. Root Cause #6: Double Initialization on Fallback-to-Demo Path (LOW) — NEW

### 9.1 Discovery

**Not identified by Phase 2 analysis.**

### 9.2 Evidence

In `main.py:165-180`, the startup lifespan has a flow where, if the cascor probe fails,
the backend falls back to demo mode:

```python
# main.py:165-180
if cascor_url and backend.backend_type == "service":
    cascor_probe = probe_dependency("JuniperCascor", ...)
    if cascor_probe.status == "healthy":
        ...
    else:
        await backend.shutdown()
        backend = create_backend(demo_mode=True)
        await backend.initialize()     # ← First init (inside fallback branch)

# Initialize the backend
await backend.initialize()              # ← Second init (unconditional, line 180)
```

When the cascor probe fails and the backend falls back to demo mode:

1. `backend.initialize()` is called at line 177 (inside the fallback block)
2. `backend.initialize()` is called again at line 180 (unconditionally)

### 9.3 Impact

For `DemoBackend`, `initialize()` calls `self._demo.start()`, which starts the training
simulation thread. Calling it twice could start two simulation threads or produce unexpected
state depending on `DemoMode.start()`'s idempotency guarantees.

### 9.4 Scope Limitation

This bug only affects the **fallback-to-demo path** (cascor unreachable). Normal service
mode and normal demo mode (configured from the start) are not affected.

### 9.5 Severity Rationale

LOW because:

- It only affects the fallback path
- It is not related to the external cascor display problem
- The impact depends on whether `DemoMode.start()` is idempotent

---

## 10. Root Cause #7: No Canonical Metric Contract Enforcement (SYSTEMIC) — NEW

### 10.1 Discovery

**Not identified by Phase 2 analysis.** This is the architectural root cause underlying
RC-1, RC-4, and RC-5.

### 10.2 Evidence

There are at least four distinct ingress paths for metric data into canopy, each
independently determining the output format:

| # | Ingress Path                       | Current Format | Code Location                                                           |
|---|------------------------------------|----------------|-------------------------------------------------------------------------|
| 1 | REST metrics history (polling)     | Flat           | `_ServiceTrainingMonitor.get_recent_metrics()` → `_normalize_metric()`  |
| 2 | REST current metrics (polling)     | Flat           | `_ServiceTrainingMonitor.get_current_metrics()` → `_normalize_metric()` |
| 3 | State sync on connect              | Raw cascor     | `CascorStateSync.sync()` — no normalization                             |
| 4 | WebSocket relay (metrics messages) | Raw cascor     | Relay broadcasts raw message data                                       |

Demo mode has a single ingress path that produces the nested format:

| # | Ingress Path       | Current Format | Code Location                                       |
|---|--------------------|----------------|-----------------------------------------------------|
| 1 | Demo training loop | Nested         | `DemoMode._compute_and_emit_metrics()` at line 1162 |

There is **no shared function or contract** that enforces all paths to produce the same
output shape. Each path independently decides its format.

### 10.3 Architectural Consequence

- The Phase 1 plan created `_normalize_metric()` as a normalization boundary, but it
  normalizes to the **wrong target format** (flat instead of nested)
- The Phase 1 plan did not require all ingress paths to pass through the normalization
  boundary (state sync and WebSocket relay bypass it)
- Adding a new ingress path in the future has no guardrail ensuring format consistency

### 10.4 Recommended Architectural Fix

Create a single shared metric formatter that:

1. Accepts any known input format (raw cascor, flat normalized, or already-nested)
2. Produces the **nested** format the dashboard expects
3. Is called from **all** metric ingress paths

Suggested location: `backend/metric_contract.py` or integrate into the existing
`_normalize_metric()` method by adding a nesting step.

---

## 11. Status Bar Data Path — Verified Working

For completeness, the status bar data path was verified as **correctly functioning**:

```bash
1. Dashboard polls: GET /api/status (every 1s)
2. main.py:620-627 → return backend.get_status()
3. ServiceBackend.get_status() (service_backend.py:100-136) → REST call to cascor
4. Transforms nested cascor response to flat dict with correct key names
5. dashboard_manager.py:1510-1576 → Reads flat keys that match service backend output
6. Status bar displays correctly ✓
```

The status bar works because `ServiceBackend.get_status()` was correctly designed to produce
the exact key names that `_build_unified_status_bar_content()` reads:

| Dashboard Key     | Service Backend Key | Match |
|-------------------|---------------------|-------|
| `is_running`      | `is_running`        | ✅    |
| `is_paused`       | `is_paused`         | ✅    |
| `completed`       | `completed`         | ✅    |
| `failed`          | `failed`            | ✅    |
| `phase`           | `phase`             | ✅    |
| `current_epoch`   | `current_epoch`     | ✅    |
| `hidden_units`    | `hidden_units`      | ✅    |

**Key insight**: The status bar works because its producer (`get_status()`) and consumer
(`_build_unified_status_bar_content()`) were designed with matching contracts. The metrics
path fails because its producer (`_normalize_metric()`) and consumer (`MetricsPanel`)
have **mismatched contracts**.

---

## 12. Phase 2 Assessment Evaluation

### 12.1 What Phase 2 Got Right

- **RC-1 (Metrics format mismatch)**: Correctly identified as CRITICAL. The analysis,
  evidence, and data flow tracing were accurate. This is confirmed as the primary blocker.
- **RC-2 (WebSocket relay omits fields)**: Correctly identified as MODERATE. The evidence
  and impact analysis were accurate.
- **RC-3 (Dashboard ignores WebSocket)**: Correctly identified as LOW. The assessment that
  HTTP polling is adequate was sound.
- **Verification of Phase 1 fixes**: The Phase 2 analysis correctly verified that all 14
  Phase 1 fixes were fully implemented.

### 12.2 What Phase 2 Missed

- **RC-4 (State sync metrics not normalized)**: The Phase 2 analysis examined state_sync.py
  but only evaluated it for status/params sync correctness. It did not check whether
  `metrics_history` was normalized.
- **RC-5 (`/api/metrics` also affected)**: The Phase 2 analysis focused on
  `/api/metrics/history` and did not trace the `/api/metrics` (current snapshot) path.
- **RC-6 (Double init on fallback)**: Not in scope of Phase 2's metrics-focused analysis,
  but relevant to overall system correctness.
- **RC-7 (No canonical contract enforcement)**: Phase 2 correctly identified the symptom
  (format mismatch) but did not elevate the analysis to the architectural level — the lack
  of a shared format contract across all ingress paths.

### 12.3 Phase 2 Accuracy Rating

**85% accurate.** The three identified root causes were all correct and well-evidenced.
The analysis missed four additional issues (two directly related to the metrics display
problem, one tangential, one architectural). The primary recommendation (Option A — normalize
at the service backend level) was the correct approach.

---

## 13. Complete Fix Recommendations

### 13.1 Priority Order

| Priority | Root Cause | Fix                                                               | Effort  |
|----------|------------|-------------------------------------------------------------------|---------|
| P0       | RC-1, RC-5 | Make `_normalize_metric()` produce nested format                  | 1-2 hrs |
| P1       | RC-7       | Use single normalization function on all metric ingress paths     | 1 hr    |
| P2       | RC-4       | Pass synced metrics_history through normalization                 | 30 min  |
| P3       | RC-2       | Forward additional fields in relay state callback                 | 30 min  |
| P4       | RC-6       | Guard fallback double-init in main.py                             | 15 min  |
| P5       | RC-3       | Future enhancement — not a blocker                                | —       |

### 13.2 Fix for RC-1 + RC-5: Nested Metric Format

Modify `_normalize_metric()` (or create a wrapper) to produce the nested format:

```python
@staticmethod
def _normalize_metric_to_dashboard(entry: dict) -> dict:
    """Normalize a metric entry to the dashboard's nested format.

    Handles raw cascor format (loss, accuracy, validation_loss, etc.),
    intermediate flat format (train_loss, train_accuracy, etc.), and
    already-nested format (metrics.loss, network_topology.hidden_units).
    """
    # If already in nested format, return as-is
    if "metrics" in entry and isinstance(entry["metrics"], dict):
        return entry

    return {
        "epoch": entry.get("epoch", 0),
        "metrics": {
            "loss": _first_defined(
                entry.get("train_loss") if "train_loss" in entry else None,
                entry.get("loss") if "loss" in entry else None,
            ),
            "accuracy": _first_defined(
                entry.get("train_accuracy") if "train_accuracy" in entry else None,
                entry.get("accuracy") if "accuracy" in entry else None,
            ),
            "val_loss": _first_defined(
                entry.get("val_loss") if "val_loss" in entry else None,
                entry.get("validation_loss") if "validation_loss" in entry else None,
            ),
            "val_accuracy": _first_defined(
                entry.get("val_accuracy") if "val_accuracy" in entry else None,
                entry.get("validation_accuracy") if "validation_accuracy" in entry else None,
            ),
        },
        "network_topology": {
            "hidden_units": entry.get("hidden_units", 0),
        },
        "phase": entry.get("phase"),
        "timestamp": entry.get("timestamp"),
    }
```

Apply this function in:

- `_ServiceTrainingMonitor.get_recent_metrics()` (line 102)
- `_ServiceTrainingMonitor.get_current_metrics()` (line 91)
- `CascorStateSync.sync()` metrics_history processing (line 121)

### 13.3 Fix for RC-6: Guard Double Init

```python
# main.py:165-180 — add early continue after fallback init
if cascor_url and backend.backend_type == "service":
    cascor_probe = probe_dependency(...)
    if cascor_probe.status == "healthy":
        ...
    else:
        await backend.shutdown()
        backend = create_backend(demo_mode=True)
        await backend.initialize()
        # Skip the unconditional init below — already initialized
else:
    await backend.initialize()
```

Or restructure to use a flag:

```python
initialized = False
if cascor_url and backend.backend_type == "service":
    ...
    if not healthy:
        backend = create_backend(demo_mode=True)
        await backend.initialize()
        initialized = True

if not initialized:
    await backend.initialize()
```

---

## 14. Risks and Guardrails

| Risk                                                             | Impact                              | Probability | Mitigation                                                                        |
|------------------------------------------------------------------|-------------------------------------|-------------|-----------------------------------------------------------------------------------|
| Fix only one ingress path, leaving others producing wrong format | Partial fix; inconsistency persists | Medium      | RC-7 fix: route ALL metric paths through single normalizer                        |
| Nested format breaks existing flat-format test assertions        | Test failures                       | High        | Update test expectations to nested format simultaneously                          |
| Demo mode regresses from shared normalization code changes       | Demo mode breaks                    | Low         | Demo already produces nested format; normalization is idempotent for nested input |
| Falsy values (epoch=0, loss=0.0) treated as missing              | Charts show gaps                    | Medium      | `_first_defined()` helper already handles this correctly                          |
| `_normalize_metric()` callers in test fixtures not updated       | Tests pass with wrong contract      | Medium      | Audit all test fixtures using `_normalize_metric()` output                        |
| Double-init fix introduces new startup path bugs                 | Service mode fails to start         | Low         | Test both normal and fallback startup paths                                       |

---

## 15. Verification Plan

### 15.1 Automated Verification

After fixes are applied:

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

### 15.2 Manual Verification

```bash
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# Terminal 2: Start canopy in service mode
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: Verify API responses
# Check metrics history returns nested format:
curl -s http://localhost:8050/api/metrics/history?limit=3 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...}, "network_topology": {"hidden_units": ...}, ...}]}

# Check current metrics:
curl -s http://localhost:8050/api/metrics | python3 -m json.tool
# Expected: {"epoch": N, "metrics": {"loss": ..., "accuracy": ...}, ...}

# Check status (should already work):
curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 15.3 Visual Verification Checklist

- [ ] Loss chart displays live training data (not flat line at 0)
- [ ] Accuracy chart displays live accuracy curve
- [ ] Current loss display shows actual value (not "0.0000")
- [ ] Current accuracy display shows actual percentage (not "0.00%")
- [ ] Hidden units count shows actual count (not always 0)
- [ ] Hidden unit addition markers appear on plots when cascade events occur
- [ ] Epoch counter shows actual epoch (verified already working via status bar)
- [ ] Status bar shows Running/Paused/Stopped correctly (verified already working)
- [ ] Phase indicator shows Output/Candidate transitions (verified already working)
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and shows correct metrics

---

## 16. Appendix: Cascor Server Response Formats

### 16.1 GET /v1/training/status Response

Cascor's `TrainingLifecycleManager.get_status()` returns:

```python
{
    "state_machine": {            # From TrainingStateMachine.get_state_summary()
        "status": "STARTED",      # STARTED | PAUSED | COMPLETED | FAILED | STOPPED
        "phase": "OUTPUT",        # OUTPUT | CANDIDATE
        ...
    },
    "monitor": {                  # From TrainingMonitor.get_current_state()
        "current_epoch": 42,
        "current_hidden_units": 3,
        "is_training": True,
        ...
    },
    "training_state": {           # From TrainingState.get_state()
        "learning_rate": 0.01,
        "max_hidden_units": 10,
        "max_epochs": 1000,
        "current_epoch": 42,
        ...
    },
    "network_loaded": True,
    "training_active": True,
}
```

Wrapped in ResponseEnvelope: `{"status": "success", "data": <above>, "meta": {...}}`

### 16.2 GET /v1/metrics/history Response

Cascor's `TrainingMonitor.get_recent_metrics()` returns a list of:

```python
{
    "epoch": 42,
    "timestamp": "2026-03-27T14:30:00",
    "loss": 0.023,                    # ← "loss" not "train_loss"
    "accuracy": 0.95,                 # ← "accuracy" not "train_accuracy"
    "learning_rate": 0.01,
    "hidden_units": 3,
    "phase": "output",
    "validation_loss": 0.028,         # ← "validation_loss" not "val_loss"
    "validation_accuracy": 0.93,      # ← "validation_accuracy" not "val_accuracy"
}
```

Wrapped in ResponseEnvelope: `{"status": "success", "data": [<above>, ...], "meta": {...}}`

### 16.3 Client Library Behavior

`JuniperCascorClient` returns the **raw JSON response** including the ResponseEnvelope.
The `_request()` method at `client.py:253-277` simply calls `response.json()` with no
unwrapping.

---

## 17. Appendix: File Reference

| File                        | Path (relative to canopy/src/)  | Role                                               |
|-----------------------------|---------------------------------|----------------------------------------------------|
| `cascor_service_adapter.py` | `backend/`                      | Wraps cascor-client, normalization boundary        |
| `service_backend.py`        | `backend/`                      | BackendProtocol for service mode                   |
| `state_sync.py`             | `backend/`                      | Initial state sync on connect                      |
| `demo_backend.py`           | `backend/`                      | BackendProtocol for demo mode                      |
| `demo_mode.py`              | `.`                             | Demo training simulation (produces nested metrics) |
| `main.py`                   | `.`                             | FastAPI app, REST endpoints, startup lifecycle     |
| `dashboard_manager.py`      | `frontend/`                     | Dash app, polling callbacks, status bar            |
| `metrics_panel.py`          | `frontend/components/`          | Metrics charts, reads nested format                |
| `client.py`                 | (juniper-cascor-client pkg)     | REST client — returns raw ResponseEnvelope         |
| `monitor.py`                | (juniper-cascor/api/lifecycle/) | TrainingMonitor — produces per-epoch metric dicts  |
| `manager.py`                | (juniper-cascor/api/lifecycle/) | TrainingLifecycleManager — get_status/get_metrics  |
| `common.py`                 | (juniper-cascor/api/models/)    | ResponseEnvelope and success_response wrapper      |
