# Root Cause Analysis: Canopy Dashboard Not Displaying External CasCor Training Progress

- **Version**: 1.0.0
- **Date**: 2026-03-27
- **Author**: Claude (AI Agent)
- **Status**: Analysis Complete — Root Causes Identified
- **Related**: `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` (prior art, partially implemented)

---

## 1. Executive Summary

Despite the extensive fixes described in `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` having
been **fully implemented** in the codebase, the juniper-canopy dashboard still does not display
training metrics from an external juniper-cascor instance.

This analysis identifies **one primary root cause** and **two secondary issues** that the
prior development plan missed entirely:

| #        | Severity     | Root Cause                                                                                       | Impact                                                                                           |
|----------|--------------|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| **RC-1** | **CRITICAL** | Metrics data format mismatch — service backend returns flat keys but dashboard reads nested keys | All metrics charts empty, loss/accuracy displays show "--" or "0", hidden unit count always 0    |
| **RC-2** | MODERATE     | WebSocket relay state callback omits `current_epoch` and other fields                            | `/api/state` returns stale epoch data in service mode                                            |
| **RC-3** | LOW          | Dashboard uses HTTP polling exclusively, ignoring the WebSocket relay entirely                   | Real-time WebSocket updates from cascor are unused; all data goes through REST polling path only |

**Why the prior plan's fixes didn't solve the problem:** The plan correctly identified and
fixed the ResponseEnvelope unwrapping issue (where `_ServiceTrainingMonitor` and `CascorStateSync`
were reading raw client responses). Those fixes are all present in the code. However, the plan
defined a "canonical internal contract" (Section 6.2) with **flat** metric keys (`train_loss`,
`train_accuracy`, `val_loss`, `val_accuracy`, `hidden_units`) — but the **dashboard code** reads
**nested** keys (`metrics.loss`, `metrics.accuracy`, `network_topology.hidden_units`). The plan
never reconciled the normalization layer's output format with the dashboard's input format.

---

## 2. Root Cause #1: Metrics Data Format Mismatch (CRITICAL)

### The Problem

The dashboard's metrics panel component reads metrics data using a **nested** structure, but the
service backend produces metrics in a **flat** structure.

### Evidence: Dashboard Expectations

The `MetricsPanel` component at `frontend/components/metrics_panel.py` reads metrics data at
9 different locations, all expecting nested keys:

| Line    | Code                                                                   | Expected Structure                        |
|---------|------------------------------------------------------------------------|-------------------------------------------|
| 1091    | `m.get("network_topology", {}).get("hidden_units", 0)`                 | `network_topology.hidden_units`           |
| 1120    | `latest.get("metrics", {}).get("loss", 0)`                             | `metrics.loss`                            |
| 1121    | `latest.get("metrics", {}).get("accuracy", 0)`                         | `metrics.accuracy`                        |
| 1122    | `latest.get("network_topology", {}).get("hidden_units", 0)`            | `network_topology.hidden_units`           |
| 1330    | `metric.get("metrics", {}).get("loss", 0)`                             | `metrics.loss` (loss plot y-axis)         |
| 1449    | `metrics_data[i-1].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units`           |
| 1450    | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)`   | `network_topology.hidden_units`           |
| 1499    | `metric.get("metrics", {}).get("accuracy", 0)`                         | `metrics.accuracy` (accuracy plot y-axis) |
| 1561-62 | `metrics_data[i-1].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units`           |

### Evidence: Demo Mode Format (What Works)

Demo mode at `demo_mode.py:1162-1177` produces metrics in the nested format the dashboard expects:

```python
metrics = {
    "epoch": self.current_epoch,
    "metrics": {                          # <-- NESTED dict
        "loss": float(loss),
        "accuracy": float(accuracy),
        "val_loss": float(val_loss),
        "val_accuracy": float(val_accuracy),
    },
    "network_topology": {                 # <-- NESTED dict
        "input_units": self.network.input_size,
        "hidden_units": len(self.network.hidden_units),
        "output_units": self.network.output_size,
    },
    "phase": phase_name,
    "timestamp": datetime.now().isoformat(),
}
```

### Evidence: Service Backend Format (What's Broken)

The service backend at `cascor_service_adapter.py:431-460` normalizes metrics to a **flat** format:

```python
# CascorServiceAdapter._normalize_metric()
return {
    "epoch": entry.get("epoch", 0),
    "train_loss": ...,          # <-- FLAT key (dashboard looks for metrics.loss)
    "train_accuracy": ...,      # <-- FLAT key (dashboard looks for metrics.accuracy)
    "val_loss": ...,            # <-- FLAT key
    "val_accuracy": ...,        # <-- FLAT key
    "hidden_units": ...,        # <-- FLAT key (dashboard looks for network_topology.hidden_units)
    "phase": ...,
    "timestamp": ...,
}
```

### The Complete Data Path (Service Mode)

```bash
1. Dashboard polls: GET /api/metrics/history?limit=100
2. main.py:640-650 → return {"history": backend.get_metrics_history(count)}
3. ServiceBackend.get_metrics_history() → self._adapter.training_monitor.get_recent_metrics(count)
4. _ServiceTrainingMonitor.get_recent_metrics() → self._client.get_metrics_history(count)
5. JuniperCascorClient → HTTP GET /v1/metrics/history → returns ResponseEnvelope
6. _normalize_metric() → converts to FLAT keys
7. Response: {"history": [{"epoch": 42, "train_loss": 0.023, ...}, ...]}
8. Dashboard receives flat metrics
9. metric.get("metrics", {}).get("loss", 0)  →  returns 0 (always!)
10. metric.get("network_topology", {}).get("hidden_units", 0)  →  returns 0 (always!)
```

### Consequence

- **Loss plot**: All y-values are `0` → flat line at zero or empty plot
- **Accuracy plot**: All y-values are `0` → flat line at zero or empty plot
- **Current loss display**: Shows "0.0000" or "--"
- **Current accuracy display**: Shows "0.00%" or "--"
- **Hidden units count**: Always shows "0"
- **Hidden unit addition markers**: Never rendered (both prev and curr are always 0)
- **Phase-based filtering**: The `phase` key IS at the top level in both formats, so phase
  filtering technically works, but with zero-valued data it doesn't matter

### Why the Development Plan Missed This

The `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` defined a "Canonical Internal Contract"
(Section 6.2) for metrics history using **flat** keys:

```python
# Plan's Section 6.2 — Metrics History Contract
[
    {
        "epoch": int,
        "train_loss": float | None,       # Flat
        "train_accuracy": float | None,    # Flat
        "val_loss": float | None,          # Flat
        "val_accuracy": float | None,      # Flat
        "hidden_units": int,               # Flat
        "phase": str | None,
        "timestamp": float | None,
    },
]
```

This contract was designed to normalize cascor's response format, but it was never validated
against the dashboard's actual input format. The plan focused on the **normalization boundary**
(unwrapping ResponseEnvelope, mapping field names) but stopped before the **last mile** — where
the normalized data meets the dashboard callbacks.

---

## 3. Root Cause #2: WebSocket Relay State Callback Omits Fields (MODERATE)

### The Problem, Root Cause #2

The WebSocket relay's state update callback only forwards `status` and `phase` to the global
`training_state`. It does not forward `current_epoch`, `current_step`, `learning_rate`,
`max_hidden_units`, `max_epochs`, or any other fields from the cascor `state` message.

### Evidencebash, Root Cause 3#2

At `cascor_service_adapter.py:218-225`:

```python
if msg_type == "state" and self._state_update_callback and isinstance(data, dict):
    try:
        from backend.state_sync import CascorStateSync
        status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
        self._state_update_callback(status=status, phase=data.get("phase", ""))
        # ^^^ Only status and phase — no current_epoch, no hidden_units, etc.
    except Exception as se:
        logger.debug(f"State update callback error: {se}")
```

The cascor server's WebSocket `state` messages include `current_epoch`, `current_step`,
`learning_rate`, `max_hidden_units`, and `max_epochs` — all of which are discarded by the
relay callback.

### Impact, Root Cause #2

- The `/api/state` endpoint in service mode reads from `training_state.get_state()` (main.py:586),
  which only receives `status` and `phase` updates via the relay callback
- After initial sync (main.py:192-199), the `current_epoch` in `training_state` becomes stale
- The parameter panel may show stale epoch/hidden unit counts if it reads from `/api/state`
  rather than `/api/status`
- **Mitigating factor**: The status bar reads from `/api/status`, which makes a fresh REST call
  to cascor each time it polls, bypassing the stale `training_state`

---

## 4. Root Cause #3: Dashboard Ignores WebSocket Relay (LOW)

### The Problem, Root Cause #3

The canopy server maintains a WebSocket relay that receives real-time updates from cascor and
broadcasts them to all connected WebSocket clients. However, the dashboard does **not** consume
these WebSocket messages for data display. Instead, it relies entirely on HTTP polling via
`dcc.Interval` callbacks.

### Evidence, Root Cause #3

The dashboard manager defines two polling intervals:

| Interval ID            | Period | Used For                                           |
|------------------------|--------|----------------------------------------------------|
| `fast-update-interval` | 1000ms | Status bar, metrics store                          |
| `slow-update-interval` | 5000ms | Network info, topology, dataset, decision boundary |

All data flows through HTTP GET requests to `/api/status`, `/api/metrics/history`, `/api/topology`,
`/api/dataset`, and `/api/decision_boundary`.

A `websocket-data` div is defined in the layout (dashboard_manager.py:876) but **no Dash callback
reads from it**. There are no `Input("websocket-data", ...)` bindings in any callback.

### Impact, Root Cause #3

- WebSocket messages from cascor are broadcast to browser clients but never consumed
- The 1-second polling interval introduces latency vs. real-time WebSocket updates
- The relay's `metrics` type messages (which use cascor's format, not demo mode's nested format)
  would still have the RC-1 format mismatch even if the dashboard did consume them
- **Not a blocker**: This is a performance/UX issue, not a functional blocker. HTTP polling at
  1-second intervals is adequate for training progress display.

---

## 5. Summary of Previously Implemented Fixes (Now Verified)

The following fixes from `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` are confirmed to be
**fully implemented and correct** in the current codebase:

| FIX ID  | File                                | Status      | Notes                                                      |
|---------|-------------------------------------|-------------|------------------------------------------------------------|
| FIX-1   | `cascor_service_adapter.py:96-108`  | Implemented | `get_recent_metrics()` handles both list and dict envelope |
| FIX-2   | `cascor_service_adapter.py:72-84`   | Implemented | `is_training` uses `is not None` guard for False           |
| FIX-3   | `cascor_service_adapter.py:86-94`   | Implemented | `get_current_metrics()` unwraps envelope                   |
| FIX-4   | `service_backend.py:100-136`        | Implemented | `get_status()` transforms nested to flat dashboard keys    |
| FIX-5   | `state_sync.py:59-92`               | Implemented | `sync()` reads nested status correctly                     |
| FIX-6   | `state_sync.py:117-127`             | Implemented | Metrics history handles both list and dict                 |
| FIX-7   | `state_sync.py:98-103`              | Implemented | Params handles both flat and nested                        |
| FIX-8   | `cascor_service_adapter.py:310-321` | Implemented | `is_training_in_progress()` uses same logic as FIX-2       |
| FIX-9   | `cascor_service_adapter.py:367`     | Implemented | Reverse param map auto-generated                           |
| FIX-10  | `cascor_service_adapter.py:386-402` | Implemented | `get_canopy_params()` dual-path logic                      |
| FIX-11  | `service_backend.py:155-168`        | Implemented | Dataset response key mapping                               |
| FIX-12  | `state_sync.py:137-154`             | Implemented | Status normalization mapping expanded                      |
| FIX-13  | `cascor_service_adapter.py:430-460` | Implemented | Metric field name normalization                            |
| FIX-SYS | `fake_client.py` (cascor-client)    | Implemented | FakeCascorClient uses ResponseEnvelope format              |

**The development plan's Phase 1 normalization helpers (`_first_defined`, `_is_cascor_nested`,
`_normalize_metric`) are all present.** The Phase 2 read-path fixes, Phase 3 state sync fixes,
and Phase 4 parameter/dataset fixes are all in place. The implementation is correct for its
stated goals — the problem is that the stated goals did not include reconciling the output
format with the dashboard's input format.

---

## 6. Status Bar Data Path (Working Correctly)

For completeness, here's the status bar data path, which **does work correctly**:

```bash
1. Dashboard polls: GET /api/status (every 1s)
2. main.py:620-627 → return backend.get_status()
3. ServiceBackend.get_status() (service_backend.py:100-136)
4. → self._adapter.get_training_status()  # REST call to cascor
5. → CascorServiceAdapter._unwrap_response()  # strips ResponseEnvelope
6. → CascorServiceAdapter._is_cascor_nested()  # detects nested structure
7. → Transforms to flat dict with is_running, is_paused, phase, current_epoch, hidden_units
8. Dashboard reads: status_data.get("is_running"), status_data.get("current_epoch"), etc.
9. Status bar updates correctly ✓
```

The status bar's `_build_unified_status_bar_content()` (dashboard_manager.py:1510-1570) reads
flat keys that match what `ServiceBackend.get_status()` produces:

| Dashboard Key Read | Service Backend Key Produced | Match? |
|--------------------|------------------------------|--------|
| `is_running`       | `is_running`                 | Yes    |
| `is_paused`        | `is_paused`                  | Yes    |
| `completed`        | `completed`                  | Yes    |
| `failed`           | `failed`                     | Yes    |
| `phase`            | `phase`                      | Yes    |
| `current_epoch`    | `current_epoch`              | Yes    |
| `hidden_units`     | `hidden_units`               | Yes    |

---

## 7. Fix Recommendations

### Fix for RC-1 (CRITICAL): Align Metrics Format

Two approaches, choose one:

**Option A — Normalize at the service backend level (recommended):**

Modify `ServiceBackend.get_metrics_history()` or `_ServiceTrainingMonitor.get_recent_metrics()`
to produce metrics in the nested format the dashboard expects. Add a transformation after
`_normalize_metric()` that restructures flat keys into the nested format:

```python
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format."""
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

**Option B — Make the dashboard read both formats:**

Modify `MetricsPanel._update_metrics_display_handler()` and the plot creation methods to
read both nested and flat keys:

```python
# Instead of:
current_loss = latest.get("metrics", {}).get("loss", 0)
# Use:
current_loss = latest.get("metrics", {}).get("loss") or latest.get("train_loss", 0)
```

**Recommendation:** Option A is preferred because it centralizes the transformation in one
place and maintains the dashboard's existing contract. Option B requires changes at 9+
locations in `metrics_panel.py`.

### Fix for RC-2 (MODERATE): Forward Additional Fields in Relay Callback

Update the relay callback in `cascor_service_adapter.py:218-225` to forward additional fields:

```python
self._state_update_callback(
    status=status,
    phase=data.get("phase", ""),
    current_epoch=data.get("current_epoch"),
    max_epochs=data.get("max_epochs"),
    learning_rate=data.get("learning_rate"),
    max_hidden_units=data.get("max_hidden_units"),
)
```

### Fix for RC-3 (LOW): Future Enhancement

Not a blocker. If real-time updates are desired in the future, implement Dash clientside
callbacks or use `dash_extensions.WebSocket` to consume the WebSocket relay messages directly.

---

## 8. Verification Plan

After applying fixes, verify:

1. **Start all services:**
   - juniper-data: `cd juniper-data && PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100`
   - juniper-cascor: `cd juniper-cascor/src && JUNIPER_CASCOR_PORT=8201 python server.py`
   - juniper-canopy: `cd juniper-canopy/src && CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050`

2. **Start training on cascor** (via cascor's auto-start or manual API call)

3. **Verify metrics endpoint returns correct format:**

   ```bash
   curl -s http://localhost:8050/api/metrics/history?limit=5 | python3 -m json.tool
   # Should see: {"history": [{"epoch": ..., "metrics": {"loss": ..., "accuracy": ...}, "network_topology": {"hidden_units": ...}}, ...]}
   ```

4. **Verify status endpoint:**

   ```bash
   curl -s http://localhost:8050/api/status | python3 -m json.tool
   # Should see: {"is_running": true, "phase": "output", "current_epoch": 42, ...}
   ```

5. **Open dashboard in browser:** `http://localhost:8050`
   - Loss chart should show training loss curve
   - Accuracy chart should show accuracy curve
   - Status bar should show "Running", current epoch, hidden units
   - Phase should show "Output Training" or "Candidate Pool"

---

## 9. Appendix: File Reference

| File                        | Path (relative to canopy/src/) | Role                                               |
|-----------------------------|--------------------------------|----------------------------------------------------|
| `cascor_service_adapter.py` | `backend/`                     | Wraps cascor-client, normalization boundary        |
| `service_backend.py`        | `backend/`                     | BackendProtocol for service mode                   |
| `state_sync.py`             | `backend/`                     | Initial state sync on connect                      |
| `demo_backend.py`           | `backend/`                     | BackendProtocol for demo mode                      |
| `demo_mode.py`              | `.`                            | Demo training simulation (produces nested metrics) |
| `main.py`                   | `.`                            | FastAPI app, REST endpoints, WebSocket handlers    |
| `dashboard_manager.py`      | `frontend/`                    | Dash app, polling callbacks, status bar            |
| `metrics_panel.py`          | `frontend/components/`         | Metrics charts, reads nested format                |
| `websocket_manager.py`      | `communication/`               | WebSocket connection management                    |
| `training_monitor.py`       | `backend/`                     | Global TrainingState class                         |
| `client.py`                 | (cascor-client pkg)            | REST client — returns raw ResponseEnvelope         |
| `ws_client.py`              | (cascor-client pkg)            | WebSocket client — CascorTrainingStream            |
| `fake_client.py`            | (cascor-client pkg)            | Test double — now uses ResponseEnvelope format     |
