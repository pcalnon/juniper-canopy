# Phase 3 Root Cause Analysis: External CasCor Display Failure

**Version**: 2.0.0
**Date**: 2026-03-27
**Author**: Claude (AI Agent -- Opus 4.6, 1M context)
**Status**: Analysis Complete -- Root Causes Verified and Expanded

---

## 1. Executive Summary

This analysis is the third phase of debugging the persistent failure of juniper-canopy's dashboard to display training metrics from an externally running juniper-cascor service instance. Despite extensive work in Phase 1 (UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md) and Phase 2 (ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md), the feature remains non-functional.

This Phase 3 investigation performed an independent, code-level trace of every data path from the cascor service through the canopy backend to the dashboard frontend. The analysis confirms Phase 2's primary finding (RC-1) and identifies two additional root causes not previously documented.

### Root Cause Summary

| ID       | Severity     | Root Cause                                                                                             | Phase 2?        | Status                                                                                                      |
|----------|--------------|--------------------------------------------------------------------------------------------------------|-----------------|-------------------------------------------------------------------------------------------------------------|
| **RC-1** | **CRITICAL** | Metrics format mismatch: service backend produces flat keys, dashboard reads nested keys               | Yes (confirmed) | **PRIMARY BLOCKER**                                                                                         |
| **RC-2** | MODERATE     | WebSocket relay callback only forwards `status` and `phase`, omitting `current_epoch` and other fields | Yes (confirmed) | Causes stale `/api/state` data                                                                              |
| **RC-3** | LOW          | Dashboard uses HTTP polling exclusively, ignoring WebSocket relay                                      | Yes (confirmed) | Not a blocker                                                                                               |
| ~~RC-4~~ | ~~MODERATE~~ | ~~`/api/state` parameter initialization uses hardcoded defaults~~                                      | ~~NEW~~         | **FALSE POSITIVE** -- code at main.py:612-614 already overlays real cascor values via `get_canopy_params()` |
| **RC-5** | LOW          | `SyncedState.metrics_history` stored without normalization                                             | **NEW**         | Latent bug (currently unused code path)                                                                     |

**Bottom line**: RC-1 alone explains the complete failure of metrics display. Fixing RC-1 will restore charts. RC-2 causes secondary display staleness in `/api/state`. RC-5 is a latent defect that will surface if synced history is ever used for display.

---

## 2. Methodology

### 2.1 Approach

Rather than reasoning from documentation, this analysis traced the actual code paths at the current project state, following data from origin (cascor REST/WebSocket APIs) through every transformation layer to the final consumer (Dash callbacks in `metrics_panel.py` and `dashboard_manager.py`).

### 2.2 Codebases Examined

| Repository                | Key Files Analyzed                                                                                                                                                                                                                                                       |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **juniper-cascor**        | `api/routes/metrics.py`, `api/routes/training.py`, `api/websocket/messages.py`, `api/lifecycle/monitor.py`, `api/lifecycle/manager.py`, `api/models/common.py`                                                                                                           |
| **juniper-cascor-client** | `client.py`, `ws_client.py`, `testing/fake_client.py`, `testing/scenarios.py`                                                                                                                                                                                            |
| **juniper-canopy**        | `backend/cascor_service_adapter.py`, `backend/service_backend.py`, `backend/state_sync.py`, `backend/demo_backend.py`, `backend/training_monitor.py` (TrainingState), `main.py`, `frontend/dashboard_manager.py`, `frontend/components/metrics_panel.py`, `demo_mode.py` |

### 2.3 Analysis Steps

1. Documented exact response shapes from cascor REST API and WebSocket messages
2. Traced data through `JuniperCascorClient` -> `_ServiceTrainingMonitor` -> `ServiceBackend` -> `main.py` API endpoints -> `dashboard_manager` HTTP fetch -> `metrics_panel` callbacks
3. Compared service-mode data format at each step against demo-mode data format (the working reference)
4. Identified every point where format divergence causes display failure
5. Evaluated Phase 2's root causes against actual code
6. Searched for additional root causes not previously identified

---

## 3. Phase 1 Evaluation

### 3.1 What Phase 1 Accomplished

The UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN correctly identified the foundational problem: the `_ServiceTrainingMonitor` and `CascorStateSync` classes were developed against `FakeCascorClient`, whose response format structurally diverges from the real cascor server's `ResponseEnvelope`. The plan prescribed a normalization boundary in `CascorServiceAdapter`.

Phase 1 delivered:

- **Response envelope unwrapping** (`_unwrap_response()`) -- correctly strips the `{"status": "success", "data": ..., "meta": ...}` wrapper
- **Nested structure detection** (`_is_cascor_nested()`) -- correctly identifies cascor's multi-level response structure
- **Metric field name normalization** (`_normalize_metric()`) -- correctly maps cascor names (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`) to canonical names (`train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`)
- **Falsy-value preservation** (`_first_defined()`) -- correctly preserves `0`, `0.0`, and `False` during normalization
- **Status normalization** (`CascorStateSync._normalize_status()`) -- correctly maps cascor state strings to canopy display strings
- **ServiceBackend.get_status() flattening** -- correctly extracts `current_epoch` and `hidden_units` from cascor's nested `state_machine`/`monitor`/`training_state` response structure

### 3.2 Why Phase 1 Did Not Solve the Problem

The plan defined a "canonical internal contract" (section 6) specifying the normalized output format:

```python
# Phase 1's canonical contract (flat keys)
{
    "epoch": int,
    "train_loss": float,
    "train_accuracy": float,
    "val_loss": float,
    "val_accuracy": float,
    "hidden_units": int,
    "phase": str,
    "timestamp": str,
}
```

This contract was designed to normalize cascor's field names but was **never validated against the dashboard's actual input expectations**. The dashboard was written to consume the demo backend's output format, which uses a fundamentally different structure:

```python
# Demo backend format (nested keys -- what the dashboard actually reads)
{
    "epoch": int,
    "metrics": {
        "loss": float,
        "accuracy": float,
        "val_loss": float,
        "val_accuracy": float,
    },
    "network_topology": {
        "hidden_units": int,
        "input_units": int,
        "output_units": int,
    },
    "phase": str,
    "timestamp": str,
}
```

The Phase 1 normalization successfully translates cascor's native field names to canonical names, but the resulting flat structure still does not match what the dashboard reads. The normalization layer sits between the wrong two layers -- it normalizes the source format without producing the target format.

---

## 4. Phase 2 Evaluation

### 4.1 RC-1: Metrics Data Format Mismatch -- CONFIRMED

Phase 2 correctly identified this as the critical root cause. The evidence chain is fully verified:

#### 4.1.1 Complete Data Flow Trace (Service Mode)

```bash
Step 1: CasCor /v1/metrics/history
        Returns: {"status":"success","data":[{"epoch":1,"loss":0.5,"accuracy":0.7,
                  "validation_loss":0.6,"validation_accuracy":0.65,"hidden_units":0,
                  "phase":"output","timestamp":"..."}],"meta":{...}}

Step 2: JuniperCascorClient.get_metrics_history()
        Returns: raw JSON with envelope (pass-through)

Step 3: _ServiceTrainingMonitor.get_recent_metrics()
        Unwraps envelope -> normalizes each entry via _normalize_metric()
        Returns: [{"epoch":1,"train_loss":0.5,"train_accuracy":0.7,
                   "val_loss":0.6,"val_accuracy":0.65,"hidden_units":0,
                   "phase":"output","timestamp":"..."}]

Step 4: ServiceBackend.get_metrics_history()
        Returns: flat list from Step 3 (pass-through)

Step 5: main.py /api/metrics/history
        Returns: {"history": [<flat dicts from Step 4>]}

Step 6: dashboard_manager._update_metrics_store_handler()
        Fetches /api/metrics/history, unwraps "history" key
        Stores flat list into metrics-panel-metrics-store (dcc.Store)

Step 7: metrics_panel._update_metrics_display_handler()
        Reads from store using NESTED access patterns:
          m.get("metrics", {}).get("loss", 0)              -> always 0
          m.get("metrics", {}).get("accuracy", 0)          -> always 0
          m.get("network_topology", {}).get("hidden_units", 0) -> always 0
```

#### 4.1.2 Dashboard Access Patterns (Evidence)

All nested access patterns in `metrics_panel.py`:

| Line      | Code                                                                 | Expected Key Path               | Flat Key Available | Result       |
|-----------|----------------------------------------------------------------------|---------------------------------|--------------------|--------------|
| 1091      | `m.get("network_topology", {}).get("hidden_units", 0)`               | `network_topology.hidden_units` | `hidden_units`     | **0** (miss) |
| 1120      | `latest.get("metrics", {}).get("loss", 0)`                           | `metrics.loss`                  | `train_loss`       | **0** (miss) |
| 1121      | `latest.get("metrics", {}).get("accuracy", 0)`                       | `metrics.accuracy`              | `train_accuracy`   | **0** (miss) |
| 1122      | `latest.get("network_topology", {}).get("hidden_units", 0)`          | `network_topology.hidden_units` | `hidden_units`     | **0** (miss) |
| 1330      | `metric.get("metrics", {}).get("loss", 0)`                           | `metrics.loss`                  | `train_loss`       | **0** (miss) |
| 1449-1450 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units`     | **0** (miss) |
| 1499      | `metric.get("metrics", {}).get("accuracy", 0)`                       | `metrics.accuracy`              | `train_accuracy`   | **0** (miss) |
| 1561-1562 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units` | `hidden_units`     | **0** (miss) |

**Flat access patterns that DO work:**

| Line                   | Code                  | Result                    |
|------------------------|-----------------------|---------------------------|
| 1093, 1119, 1329, 1498 | `m.get("epoch", 0)`   | Correct (flat key exists) |
| 1123, 1331, 1500       | `m.get("phase", ...)` | Correct (flat key exists) |

#### 4.1.3 Impact

- **Loss chart**: All y-values read as 0 -> flat line at zero or empty
- **Accuracy chart**: All y-values read as 0 -> flat line at zero or empty
- **Current loss/accuracy indicators**: Always show "0.0000" or "--"
- **Hidden unit count**: Always shows 0
- **Hidden unit addition markers**: Never rendered (hidden unit change detection always sees 0->0)

#### 4.1.4 Additional Nuance (Not in Phase 2)

The field name mapping between flat and nested formats is non-trivial:

| Flat Key (from `_normalize_metric`) | Required Nested Path (from dashboard)                       |
|-------------------------------------|-------------------------------------------------------------|
| `train_loss`                        | `metrics.loss` (note: `loss`, not `train_loss`)             |
| `train_accuracy`                    | `metrics.accuracy` (note: `accuracy`, not `train_accuracy`) |
| `val_loss`                          | `metrics.val_loss`                                          |
| `val_accuracy`                      | `metrics.val_accuracy`                                      |
| `hidden_units`                      | `network_topology.hidden_units`                             |

The `train_` prefix must be stripped when nesting under `metrics`, because the demo backend uses bare `loss` and `accuracy` names within the nested dict.

### 4.2 RC-2: WebSocket Relay State Callback Omits Fields -- CONFIRMED

Phase 2 correctly identified that the relay callback (cascor_service_adapter.py:218-225) only forwards `status` and `phase`:

```python
# Line 223 -- current implementation
self._state_update_callback(status=status, phase=data.get("phase", ""))
```

The `TrainingState` class (in `backend/training_monitor.py`) accepts 20 fields via `update_state(**kwargs)` including `current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, `max_epochs`, etc. But only `status` and `phase` are forwarded.

**Verified Impact**:

- The global `training_state` object's `current_epoch` field goes stale after the initial sync in `main.py` lifespan startup
- The `/api/state` endpoint reads from `training_state.get_state()`, so it returns stale epoch data
- **Mitigating factor**: The status bar reads from `/api/status` (which calls `ServiceBackend.get_status()`, making a **fresh REST call** to cascor), NOT from `/api/state`. So the status bar's epoch and hidden unit counts are live and accurate.
- **Actual impact is limited to**: Any consumer of `/api/state` getting stale `current_epoch`/`current_step` values after initial sync

### 4.3 RC-3: Dashboard Ignores WebSocket Relay -- CONFIRMED (LOW)

Phase 2 correctly identified that the dashboard uses HTTP polling exclusively:

- `fast-update-interval` (1000ms) triggers metrics fetch and status bar update
- `slow-update-interval` (5000ms) triggers topology and dataset updates
- No clientside JavaScript consumes WebSocket messages for data display

This is adequate for training progress display and is **not a blocker**.

---

## 5. Additional Root Causes (Not Identified in Phase 2)

### 5.1 ~~RC-4 (MODERATE)~~: `/api/state` Parameter Initialization -- FALSE POSITIVE

> **Correction (validation pass)**: Initial analysis concluded that `get_canopy_params()` was never called during initialization. This is **incorrect**. The `/api/state` endpoint in service mode (main.py:612-614) explicitly calls `get_canopy_params()` and overlays real cascor values after setting defaults:
>
> ```python
> # main.py:612-614
> canopy_params = backend._adapter.get_canopy_params()
> state.update(canopy_params)
> ```
>
> This means the 7 cascor-mappable parameters (`nn_learning_rate`, `nn_max_hidden_units`, `nn_max_total_epochs`, `nn_growth_convergence_threshold`, `cn_pool_size`, `cn_correlation_threshold`, `cn_training_iterations`) are correctly populated with live cascor values on every `/api/state` request. The remaining ~15 canopy-only parameters correctly receive defaults. **This is not a root cause.**

### 5.2 RC-5 (LOW): Synced Metrics History Stored Without Normalization

#### 5.2.1 Problem Description

`CascorStateSync.sync()` stores `metrics_history` directly from the cascor API response without applying `_normalize_metric()`:

```python
# state_sync.py:115-127
history_response = self._client.get_metrics_history(count=metrics_limit)
# ...
state.metrics_history = data  # Raw cascor format -- NOT normalized
```

#### 5.2.2 Current Impact

**None** -- `SyncedState.metrics_history` is currently unused for dashboard display. `ServiceBackend.get_metrics_history()` always fetches fresh data via `_ServiceTrainingMonitor.get_recent_metrics()`, which applies normalization.

#### 5.2.3 Risk

This is a latent defect. If a future code path (e.g., pre-populating the metrics store on connect to avoid a brief blank display) reads `synced.metrics_history`, it would receive raw cascor-format data (with `loss` instead of `train_loss`, etc.) rather than the normalized format. Given that normalization also produces the wrong format for the dashboard (RC-1), this is a double latent issue -- even normalizing the synced history would still produce flat keys.

---

## 6. Status Bar Analysis (Verified Working)

The status bar pipeline is confirmed to work correctly in service mode:

```bash
fast-update-interval (1000ms)
  -> _update_unified_status_bar_handler()
    -> HTTP GET /api/status
      -> ServiceBackend.get_status()
        -> CascorServiceAdapter.get_training_status()
          -> JuniperCascorClient.get_training_status()  (FRESH REST call)
        -> _unwrap_response() strips envelope
        -> _is_cascor_nested() detects nested structure
        -> Extracts: current_epoch from monitor.current_epoch
                     hidden_units from monitor.current_hidden_units
                     is_running from training_active
                     phase from state_machine.phase
      -> Returns flat dict with boolean flags + values
    -> _build_unified_status_bar_content()
      -> Reads: status_data.get("current_epoch", 0)  (correct)
               status_data.get("hidden_units", 0)    (correct)
               status_data.get("is_running", False)   (correct)
               status_data.get("phase", "idle")       (correct)
```

The status bar correctly displays: status indicator, status text, phase, epoch counter, and hidden unit count. This pipeline makes fresh REST calls to cascor on every poll and does not depend on the stale `training_state` or the broken metrics format.

---

## 7. Evidence Inventory

### 7.1 Code Evidence

| Evidence ID | File                          | Lines                                             | Description                                                                                                               |
|-------------|-------------------------------|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| E-1         | `cascor_service_adapter.py`   | 431-460                                           | `_normalize_metric()` produces flat keys                                                                                  |
| E-2         | `metrics_panel.py`            | 1091, 1120-1122, 1330, 1449-1450, 1499, 1561-1562 | Dashboard reads nested `metrics.loss`, `network_topology.hidden_units`                                                    |
| E-3         | `demo_mode.py`                | 1162-1177                                         | Demo backend produces nested format (working reference)                                                                   |
| E-4         | `cascor_service_adapter.py`   | 218-225                                           | Relay callback sends only `status` and `phase`                                                                            |
| E-5         | `backend/training_monitor.py` | 223-346                                           | `TrainingState` accepts 20 fields but only receives 2 from relay                                                          |
| E-6         | `main.py`                     | 589-614                                           | `/api/state` sets nn\_\*/cn\_\* defaults then overlays live cascor values via `get_canopy_params()` (RC-4 false positive) |
| E-7         | `cascor_service_adapter.py`   | 386-402                                           | `get_canopy_params()` correctly maps cascor->canopy namespace; called at main.py:613                                      |
| E-8         | `state_sync.py`               | 115-127                                           | `metrics_history` stored raw without normalization                                                                        |
| E-9         | `service_backend.py`          | 141-142                                           | `get_metrics_history()` always fetches fresh, never uses synced history                                                   |
| E-10        | `service_backend.py`          | 100-136                                           | `get_status()` correctly extracts epoch/hidden_units from cascor response                                                 |
| E-11        | `dashboard_manager.py`        | 1681-1711                                         | Metrics store handler correctly unwraps `history` envelope                                                                |
| E-12        | `dashboard_manager.py`        | 1510-1590                                         | Status bar correctly reads flat fields from `/api/status`                                                                 |

### 7.2 Comparison: Demo vs Service Format

| Field               | Demo Format (Working)           | Service Format (Broken) | Dashboard Reads                 |
|---------------------|---------------------------------|-------------------------|---------------------------------|
| Training loss       | `metrics.loss`                  | `train_loss` (flat)     | `metrics.loss`                  |
| Training accuracy   | `metrics.accuracy`              | `train_accuracy` (flat) | `metrics.accuracy`              |
| Validation loss     | `metrics.val_loss`              | `val_loss` (flat)       | Not currently read              |
| Validation accuracy | `metrics.val_accuracy`          | `val_accuracy` (flat)   | Not currently read              |
| Hidden units        | `network_topology.hidden_units` | `hidden_units` (flat)   | `network_topology.hidden_units` |
| Input units         | `network_topology.input_units`  | Not present             | `network_topology.input_units`  |
| Output units        | `network_topology.output_units` | Not present             | Not currently read              |
| Epoch               | `epoch` (flat)                  | `epoch` (flat)          | `epoch` -- **works**            |
| Phase               | `phase` (flat)                  | `phase` (flat)          | `phase` -- **works**            |
| Timestamp           | `timestamp` (flat)              | `timestamp` (flat)      | `timestamp` -- **works**        |

---

## 8. Phase 2 Fix Recommendations: Assessment

### 8.1 RC-1 Fix: Option A (Normalize at Service Backend Level)

Phase 2 recommended adding a `_to_dashboard_metric()` transformation after `_normalize_metric()`:

```python
def _to_dashboard_metric(flat: dict) -> dict:
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

**Assessment**: This is the correct approach. Advantages:

- **Single transformation point**: All metrics pass through one function
- **Preserves normalization layer**: `_normalize_metric()` continues to handle cascor->canonical mapping; `_to_dashboard_metric()` handles canonical->dashboard mapping
- **Minimal blast radius**: Only `_ServiceTrainingMonitor.get_recent_metrics()` and `.get_current_metrics()` need to apply the transformation
- **Testable**: Both transformations are static methods, easily unit-tested independently

**Risk**: The `network_topology` dict in service mode would only have `hidden_units`, missing `input_units` and `output_units` that the demo backend includes. However, the dashboard currently only reads `hidden_units` from `network_topology`, so this is not a functional gap.

### 8.2 RC-2 Fix: Forward Additional Fields

Phase 2 recommended forwarding more fields in the relay callback. **Assessment**: Correct but low priority -- the status bar already works via fresh REST calls. The fix would improve `/api/state` accuracy for epoch tracking.

### 8.3 RC-3: No Fix Needed

Phase 2 correctly classified this as a future enhancement. Agreed.

---

## 9. Recommended Fix Strategy

### Priority Order

1. **RC-1** (CRITICAL) -- Fix first. This alone will restore metrics charts.
2. **RC-2** (MODERATE) -- Fix second. Keeps `training_state` live for all fields.
3. **RC-5** (LOW) -- Fix opportunistically. Normalize synced history for consistency.
4. **RC-3** (LOW) -- Future enhancement. Not required for feature to work.

> Note: RC-4 was determined to be a false positive during validation (see section 5.1). No fix needed.

### RC-1 Fix: Recommended Implementation

Add `_to_dashboard_metric()` as a static method on `CascorServiceAdapter`, then apply it in `_ServiceTrainingMonitor`:

**File**: `cascor_service_adapter.py`

```python
@staticmethod
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format.

    The dashboard (metrics_panel.py) reads metrics using nested access:
      m.get("metrics", {}).get("loss", 0)
      m.get("network_topology", {}).get("hidden_units", 0)

    This matches the DemoBackend's output format.
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

Then update `_ServiceTrainingMonitor`:

```python
def get_current_metrics(self) -> Dict[str, Any]:
    # ... existing normalization ...
    return CascorServiceAdapter._to_dashboard_metric(
        CascorServiceAdapter._normalize_metric(data)
    )

def get_recent_metrics(self, count: int = 100) -> list:
    # ... existing normalization ...
    return [
        CascorServiceAdapter._to_dashboard_metric(
            CascorServiceAdapter._normalize_metric(m)
        )
        for m in entries
    ]
```

### RC-2 Fix: Expand Relay Callback Fields

**File**: `cascor_service_adapter.py`, line 223:

```python
# Current:
self._state_update_callback(status=status, phase=data.get("phase", ""))

# Fixed:
self._state_update_callback(
    status=status,
    phase=data.get("phase", ""),
    current_epoch=data.get("current_epoch"),
    learning_rate=data.get("learning_rate"),
    max_hidden_units=data.get("max_hidden_units"),
    max_epochs=data.get("max_epochs"),
)
```

Note: `TrainingState.update_state()` silently ignores `None` values, so passing fields that cascor doesn't include in its WebSocket state message is safe.

---

## 10. Risk Assessment

### 10.1 Fix Risks

| Risk                                                                            | Likelihood | Impact                                    | Mitigation                                                                                                                        |
|---------------------------------------------------------------------------------|------------|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `_to_dashboard_metric()` introduces None values in nested dict                  | Medium     | Loss/accuracy show as "None" instead of 0 | Use `flat.get("train_loss")` -- will be `None` only if cascor genuinely has no data. Dashboard `.get("loss", 0)` falls back to 0. |
| Demo backend tests break due to format enforcement                              | Low        | Test failures                             | Demo backend already produces the correct format; no changes needed there                                                         |
| Expanded relay callback sends `None` for fields not in cascor WebSocket message | Low        | Silent no-op                              | `TrainingState.update_state()` ignores `None` by design                                                                           |
| Future dashboard code reads flat keys, breaking on nested format                | Medium     | Localized regression                      | Add comment documenting canonical dashboard format in `_to_dashboard_metric()`                                                    |

### 10.2 Guardrails

1. **Write characterization tests first**: Before applying RC-1 fix, add tests that assert the dashboard format with nested keys. These tests should fail with the current code and pass after the fix.
2. **Verify demo mode unaffected**: Run full demo-mode test suite after changes to confirm no regression.
3. **Test with FakeCascorClient**: The fake client produces envelope-wrapped responses matching real cascor, so it can validate the full normalization pipeline.
4. **API contract test**: Add an integration test that starts ServiceBackend with FakeCascorClient and asserts `/api/metrics/history` returns metrics with nested `metrics.loss` keys.
5. **Manual E2E verification**: After fix, verify with a live cascor service that loss and accuracy charts show non-zero curves.

---

## 11. Advantages and Disadvantages of the Two-Layer Normalization Design

### Advantages

- **Separation of concerns**: `_normalize_metric()` handles source format variations (cascor vs canopy field names); `_to_dashboard_metric()` handles target format requirements (flat vs nested)
- **Testability**: Each layer can be unit-tested independently with known inputs/outputs
- **Forward compatibility**: If a new consumer needs flat format, it can call `_normalize_metric()` without `_to_dashboard_metric()`
- **Minimal invasiveness**: Changes are confined to `_ServiceTrainingMonitor` methods; no changes to `ServiceBackend`, `main.py`, or dashboard code

### Disadvantages

- **Double transformation overhead**: Every metric passes through two dict-building functions. For 1000 metrics at 1-second poll intervals, this is negligible (~<1ms).
- **Indirection**: Developers must understand the two-layer pipeline to debug data issues
- **Divergent demo/service paths**: Demo backend directly produces nested format; service backend normalizes then nests. If the dashboard format evolves, both paths must be updated.

---

## 12. Conclusions

1. **The Phase 2 analysis is correct in its primary finding (RC-1)** and its severity assessment (CRITICAL). The flat-to-nested format mismatch is the sole reason metrics charts are empty in service mode.

2. **The Phase 2 analysis is correct but slightly overstates RC-2's impact.** The status bar works correctly because it uses `/api/status` (fresh REST calls), not `/api/state` (stale `training_state`). RC-2's actual impact is limited to the `/api/state` endpoint's epoch staleness.

3. **One additional root cause (RC-5) exists** that Phase 2 did not identify. RC-5 (raw synced history) is a latent defect. An initially suspected RC-4 (parameter defaults) was determined to be a false positive during validation -- the code already overlays real cascor values via `get_canopy_params()` at main.py:612-614.

4. **The Phase 2 fix recommendation for RC-1 (Option A) is correct** and is the recommended approach. It centralizes the transformation in one place and requires no dashboard-side changes.

5. **The status bar subsystem is functional** and does not require fixes for the core connect-and-display requirement to be met.

6. **Fixing RC-1 alone will restore the primary functionality**: metrics charts will display training loss, accuracy, and hidden unit progression from an external cascor instance. RC-2 should be addressed for full production quality but is not a prerequisite for the feature to work.

---

## Appendix A: File Reference

| File                        | Path                                      | Role in Data Flow                                     |
|-----------------------------|-------------------------------------------|-------------------------------------------------------|
| `cascor_service_adapter.py` | `juniper-canopy/src/backend/`             | Normalization layer, WebSocket relay, REST delegation |
| `service_backend.py`        | `juniper-canopy/src/backend/`             | BackendProtocol wrapper, status extraction            |
| `state_sync.py`             | `juniper-canopy/src/backend/`             | One-time state sync on connect                        |
| `training_monitor.py`       | `juniper-canopy/src/backend/`             | Global TrainingState class                            |
| `demo_backend.py`           | `juniper-canopy/src/backend/`             | Working reference implementation                      |
| `demo_mode.py`              | `juniper-canopy/src/`                     | Demo training simulation (produces nested format)     |
| `main.py`                   | `juniper-canopy/src/`                     | API endpoints, lifespan, state sync                   |
| `dashboard_manager.py`      | `juniper-canopy/src/frontend/`            | HTTP polling, store population, status bar            |
| `metrics_panel.py`          | `juniper-canopy/src/frontend/components/` | Metrics chart rendering (nested format consumer)      |
| `client.py`                 | `juniper-cascor-client/`                  | REST client for cascor service                        |
| `ws_client.py`              | `juniper-cascor-client/`                  | WebSocket streaming client                            |
| `fake_client.py`            | `juniper-cascor-client/testing/`          | In-memory test fake (envelope format)                 |

## Appendix B: Prior Analysis Documents

| Document                                       | Path                    | Phase   | Status                                                                              |
|------------------------------------------------|-------------------------|---------|-------------------------------------------------------------------------------------|
| UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md    | `juniper-canopy/notes/` | Phase 1 | Implemented; fixes necessary but insufficient                                       |
| ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md | `juniper-canopy/notes/` | Phase 2 | RC-1 confirmed critical; RC-2/RC-3 confirmed; see section 4 for detailed evaluation |
| PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR.md | `juniper-canopy/notes/` | Phase 3 | This document                                                                       |
