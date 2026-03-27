# Comprehensive Root Cause Analysis: External CasCor Display Failure

**Version**: 1.0.0
**Date**: 2026-03-27
**Author**: Claude (AI Agent, Opus 4.6) -- Independent Comprehensive Analysis
**Status**: Analysis Complete -- Root Causes Identified and Validated
**Predecessors**: `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` (Phase 1), `ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md` (Phase 2)
**Codebase Versions**: juniper-canopy `ac850d34`, juniper-cascor `01474d1f`, juniper-cascor-client `8b297524`

---

## 1. Executive Summary

This analysis is an independent, comprehensive investigation into the critical requirement
that juniper-canopy connect to and display real-time training data from an external
juniper-cascor service. Despite 14 response envelope fixes (Phase 1) and a follow-up root
cause analysis identifying 3 issues (Phase 2), the dashboard still fails to display metrics,
topology, and training state from a live cascor instance.

This analysis independently verified every claim from Phase 2, confirmed its three root
causes, and identified **eight additional root causes** not previously documented. All findings
include exact code locations, evidence traces, and proposed remediation strategies.

### Key Findings

| ID        | Severity     | Root Cause                                                           | Phase 2?                   |
|-----------|--------------|----------------------------------------------------------------------|----------------------------|
| **RC-1**  | **CRITICAL** | Metrics data format mismatch (flat keys vs nested keys)              | Correctly identified       |
| **RC-4**  | **HIGH**     | Uppercase status normalization gap in WebSocket relay path           | **NEW**                    |
| **RC-2**  | MODERATE     | WebSocket relay state callback omits fields                          | Correctly identified       |
| **RC-5**  | MODERATE     | Network topology key name mismatch (`input_units` vs `input_size`)   | **NEW**                    |
| **RC-6**  | MODERATE     | Dataset scatter plot empty (metadata-only, no data arrays)           | **NEW** (known limitation) |
| **RC-7**  | MODERATE     | Hardcoded `localhost:8050` URLs in MetricsPanel                      | **NEW**                    |
| **RC-8**  | LOW          | WebSocket relay broadcasts unnormalized metric field names           | **NEW**                    |
| **RC-9**  | LOW          | Dead parameter mapping: `cn_training_iterations`/`candidate_epochs`  | **NEW**                    |
| **RC-10** | LOW          | `candidate_learning_rate` updatable on cascor but unmapped in canopy | **NEW**                    |
| **RC-3**  | LOW          | Dashboard uses HTTP polling only, ignores WebSocket relay            | Correctly identified       |
| **RC-11** | INFO         | Dual status normalization paths produce inconsistent representations | **NEW**                    |

**Bottom line**: Phase 2 correctly identified the single most critical blocker (RC-1). However,
even after fixing RC-1, **at least four additional issues** (RC-4, RC-5, RC-7, and the structural
aspects of RC-2) would prevent full functionality of the external cascor display feature.

---

## 2. Methodology

### 2.1 Analysis Approach

1. **Documentation review**: Read and analyzed both Phase 1 and Phase 2 documents in their entirety
2. **Multi-codebase deep-dive**: Traced complete data flows across juniper-canopy (frontend +
   backend), juniper-cascor (API + lifecycle), and juniper-cascor-client (REST + WebSocket clients)
   using specialized parallel sub-agents
3. **Cross-validation**: Compared actual code against both analysis documents' claims
4. **Format contract verification**: Compared producer output formats against consumer input
   expectations for every data path (metrics, status, topology, dataset, decision boundary, parameters)
5. **End-to-end tracing**: For each data path, traced from cascor's internal state through API
   serialization, client deserialization, canopy adapter normalization, REST endpoint response,
   dashboard callback polling, to frontend component rendering

### 2.2 Scope

| Component               | Files Analyzed                                                                                                                                                                            | Key Areas                                                           |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| juniper-canopy backend  | `cascor_service_adapter.py`, `service_backend.py`, `state_sync.py`, `main.py`                                                                                                             | Response normalization, status mapping, relay loop, API endpoints   |
| juniper-canopy frontend | `dashboard_manager.py`, `metrics_panel.py`, `network_visualizer.py`, `dataset_plotter.py`, `decision_boundary.py`, `websocket_client.js`                                                  | Callback data consumption, expected key formats                     |
| juniper-cascor API      | `routes/training.py`, `routes/metrics.py`, `routes/network.py`, `lifecycle/manager.py`, `lifecycle/monitor.py`, `lifecycle/state_machine.py`, `websocket/messages.py`, `models/common.py` | Response envelope structure, field names, WebSocket message formats |
| juniper-cascor-client   | `client.py`, `ws_client.py`, `testing/fake_client.py`, `testing/scenarios.py`                                                                                                             | Client interface, fake client fidelity                              |

---

## 3. Phase 1 Fix Verification

All 14 fixes from `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` were verified as **correctly
implemented** in the current codebase:

| Fix     | Description                                               | Status      | Location                                   |
|---------|-----------------------------------------------------------|-------------|--------------------------------------------|
| FIX-1   | `get_recent_metrics()` handles both bare list and dict    | Implemented | `cascor_service_adapter.py:96-108`         |
| FIX-2   | `is_training` property with `is not None` guard           | Implemented | `cascor_service_adapter.py:72-84`          |
| FIX-3   | `get_current_metrics()` unwraps envelope + normalizes     | Implemented | `cascor_service_adapter.py:86-94`          |
| FIX-4   | `get_status()` transforms nested to flat                  | Implemented | `service_backend.py:100-136`               |
| FIX-5   | `sync()` navigates nested cascor structure                | Implemented | `state_sync.py:59-92`                      |
| FIX-6   | Metrics history handles both response formats             | Implemented | `state_sync.py:106-120`                    |
| FIX-7   | Training params handles both response formats             | Implemented | `state_sync.py:95-105`                     |
| FIX-8   | `is_training_in_progress()` mirrors FIX-2 logic           | Implemented | `cascor_service_adapter.py:310-321`        |
| FIX-9   | Reverse param map auto-generated (not manual)             | Implemented | `cascor_service_adapter.py:367`            |
| FIX-10  | `get_canopy_params()` dual-path harmonized                | Implemented | `cascor_service_adapter.py:370-405`        |
| FIX-11  | Dataset response key mapping                              | Implemented | `service_backend.py:155-168`               |
| FIX-12  | Status normalization with `.lower()` in sync path         | Implemented | `state_sync.py:70, 134-154`                |
| FIX-13  | Metric field name normalization via `_normalize_metric()` | Implemented | `cascor_service_adapter.py:430-460`        |
| FIX-SYS | FakeCascorClient aligned with real server envelope        | Implemented | `fake_client.py` (ResponseEnvelope format) |

**Assessment**: Phase 1 fixes are correct and complete. They solved the ResponseEnvelope
unwrapping problem. The remaining issues are at different layers of the stack -- specifically,
the "last mile" between normalized data and dashboard component expectations.

---

## 4. Phase 2 Root Cause Verification

### 4.1 RC-1 (CRITICAL) -- Metrics Data Format Mismatch: CONFIRMED

**Phase 2 claim**: Service backend normalizes metrics to flat keys (`train_loss`,
`train_accuracy`, `hidden_units`) but MetricsPanel reads nested keys (`metrics.loss`,
`metrics.accuracy`, `network_topology.hidden_units`).

**Verdict: CONFIRMED -- correctly identified as the primary blocker.**

**Complete data path trace**:

```bash
Step 1: CasCor TrainingMonitor.on_epoch_end() records:
        {"epoch": 1, "loss": 0.543, "accuracy": 0.612, "validation_loss": 0.567, ...}

Step 2: CasCor GET /v1/metrics/history wraps in ResponseEnvelope:
        {"status": "success", "data": [<metric entries>], "meta": {...}}

Step 3: juniper-cascor-client returns response.json()

Step 4: _ServiceTrainingMonitor.get_recent_metrics() [cascor_service_adapter.py:96-108]:
        - Calls _unwrap_response() -> strips envelope -> bare list
        - Calls _normalize_metric() on each entry
        - Returns: [{"epoch": 1, "train_loss": 0.543, "train_accuracy": 0.612, ...}]
                     ^^^ FLAT keys ^^^

Step 5: ServiceBackend.get_metrics_history() passes through unchanged

Step 6: main.py GET /api/metrics/history wraps: {"history": [<flat dicts>]}

Step 7: dashboard_manager unwraps payload["history"] into metrics-panel-metrics-store

Step 8: MetricsPanel reads [metrics_panel.py:1120]:
        latest.get("metrics", {}).get("loss", 0) -> {}.get("loss", 0) -> 0
                                                      ^^^ ALWAYS 0 ^^^
```

**All 9 nested-key access locations in MetricsPanel**:

| Line      | Access Pattern                                                       | Result with Flat Data |
|-----------|----------------------------------------------------------------------|-----------------------|
| 1091      | `m.get("network_topology", {}).get("hidden_units", 0)`               | Always 0              |
| 1120      | `latest.get("metrics", {}).get("loss", 0)`                           | Always 0              |
| 1121      | `latest.get("metrics", {}).get("accuracy", 0)`                       | Always 0              |
| 1122      | `latest.get("network_topology", {}).get("hidden_units", 0)`          | Always 0              |
| 1330      | `metric.get("metrics", {}).get("loss", 0)`                           | Always 0              |
| 1449-1450 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | Always 0              |
| 1499      | `metric.get("metrics", {}).get("accuracy", 0)`                       | Always 0              |
| 1561-1562 | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)` | Always 0              |

**Why demo mode works**: `demo_mode.py:1162-1178` produces the nested format:

```python
metrics = {
    "epoch": self.current_epoch,
    "metrics": {"loss": float(loss), "accuracy": float(accuracy), ...},
    "network_topology": {"hidden_units": len(self.network.hidden_units), ...},
    "phase": phase_name,
}
```

**Format comparison table**:

| Key Path     | MetricsPanel reads                      | Demo produces                           | Service backend produces     |
|--------------|-----------------------------------------|-----------------------------------------|------------------------------|
| Loss         | `m["metrics"]["loss"]`                  | `m["metrics"]["loss"]`                  | `m["train_loss"]` (flat)     |
| Accuracy     | `m["metrics"]["accuracy"]`              | `m["metrics"]["accuracy"]`              | `m["train_accuracy"]` (flat) |
| Val loss     | `m["metrics"]["val_loss"]`              | `m["metrics"]["val_loss"]`              | `m["val_loss"]` (flat)       |
| Val accuracy | `m["metrics"]["val_accuracy"]`          | `m["metrics"]["val_accuracy"]`          | `m["val_accuracy"]` (flat)   |
| Hidden units | `m["network_topology"]["hidden_units"]` | `m["network_topology"]["hidden_units"]` | `m["hidden_units"]` (flat)   |

---

### 4.2 RC-2 (MODERATE) -- WebSocket Relay State Callback Omits Fields: CONFIRMED

**Phase 2 claim**: The relay callback only forwards `status` and `phase`, discarding
`current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, `max_epochs`.

**Verdict: CONFIRMED.**

**Evidence** at `cascor_service_adapter.py:218-225`:

```python
if msg_type == "state" and self._state_update_callback and isinstance(data, dict):
    try:
        from backend.state_sync import CascorStateSync
        status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
        self._state_update_callback(status=status, phase=data.get("phase", ""))
    except Exception as se:
        logger.debug(f"State update callback error: {se}")
```

CasCor's `state` WebSocket messages include `current_epoch`, `current_step`, `learning_rate`,
`max_hidden_units`, `max_epochs`, `network_name`, `timestamp` -- all discarded.

`TrainingState.update_state()` accepts `**kwargs` and has all these fields defined. The
callback receiver CAN handle the additional fields -- they are simply not being sent.

**Mitigation**: The status bar polls `/api/status` every 1s via `fast-update-interval`, which
calls `ServiceBackend.get_status()` making a fresh REST call. So the status bar displays
correctly. But `training_state` (global) has stale epoch/hidden unit data between REST polls.

---

### 4.3 RC-3 (LOW) -- Dashboard Uses HTTP Polling Exclusively: CONFIRMED

**Phase 2 claim**: Dashboard uses HTTP polling, does not consume WebSocket for data display.

**Verdict: CONFIRMED. Not a functional blocker.**

Two polling intervals drive all data updates:

- `fast-update-interval` (1000ms): status bar, metrics store
- `slow-update-interval` (5000ms): topology, dataset, decision boundary

`websocket-data` div exists at `dashboard_manager.py:876` but has zero Dash callback bindings.

---

## 5. Newly Identified Root Causes

### 5.1 RC-4 (HIGH) -- Uppercase Status Normalization Gap in WebSocket Relay Path

**Description**: The relay callback passes raw status strings from cascor's WebSocket messages
to `_normalize_status()` without lowercasing. The mapping only contains lowercase and
title-case keys. CasCor's state machine sends uppercase status values.

**Evidence**:

Relay callback at `cascor_service_adapter.py:222`:

```python
status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
```

Raw value passed directly -- no `.lower()` call.

The `_normalize_status()` mapping at `state_sync.py:137-153`:

```python
mapping = {
    "idle": "Stopped",      # lowercase only
    "training": "Started",
    "started": "Started",
    "paused": "Paused",
    "completed": "Completed",
    "failed": "Failed",
    "stopped": "Stopped",
    "running": "Started",
    "Stopped": "Stopped",   # title-case handled
    "Started": "Started",
    "Paused": "Paused",
    "Completed": "Completed",
    "Failed": "Failed",
}
# No uppercase keys: "STARTED", "PAUSED", "COMPLETED", etc.
```

CasCor's `TrainingStateMachine` at `lifecycle/state_machine.py` uses uppercase status enum
values: `STOPPED`, `STARTED`, `PAUSED`, `COMPLETED`, `FAILED`. The `FakeCascorClient` at
`fake_client.py:462-467` confirms: `status_map = {"training": "STARTED", "paused": "PAUSED",
"complete": "COMPLETED", "idle": "IDLE"}`.

**Contrast**: `sync()` at `state_sync.py:70` explicitly calls `.lower()` before lookup:

```python
raw_state = ... or (sm.get("status", "").lower() if isinstance(sm, dict) else None) ...
```

And `ServiceBackend.get_status()` at `service_backend.py:108` uses its own uppercase path:

```python
status_upper = fsm_status.upper() if isinstance(fsm_status, str) else "STOPPED"
```

**Impact**: When cascor broadcasts `"status": "STARTED"` via WebSocket, the relay's
`_normalize_status("STARTED")` falls through to default `"Stopped"`. The global
`training_state` is updated to `status="Stopped"` even though training is active. This
affects:

- Initial state sent to newly connecting dashboard WebSocket clients (`main.py:354`)
- `/api/state` endpoint in its fallback path
- Any component reading `training_state.get_state()` directly

**Fix**: Add `.lower()` before `_normalize_status()`:

```python
raw = data.get("status", data.get("state", ""))
status = CascorStateSync._normalize_status(raw.lower() if isinstance(raw, str) else "")
```

---

### 5.2 RC-5 (MODERATE) -- Network Topology Key Name Mismatch

**Description**: The service backend passes through cascor's topology response without key
remapping, but `NetworkVisualizer` expects different key names for unit counts.

**Evidence**:

`CascorServiceAdapter.extract_network_topology()` at `cascor_service_adapter.py:480-484`:

```python
def extract_network_topology(self) -> Optional[Dict[str, Any]]:
    try:
        return self._unwrap_response(self._client.get_topology())
    except JuniperCascorClientError:
        return None
```

No transformation. Raw passthrough after envelope unwrapping.

CasCor topology format (from `fake_client.py` and cascor service `lifecycle/manager.py`):

```python
{
    "input_size": 2,          # <-- cascor key name
    "output_size": 1,         # <-- cascor key name
    "hidden_units": 3,        # matches (but may be int count or list of unit objects)
    "layers": [...],
    "nodes": [...],
    "connections": [...],     # with "from", "to", "weight" sub-keys
    "total_connections": 11,
}
```

`NetworkVisualizer._create_network_graph()` at `network_visualizer.py:577-579`:

```python
n_input = topology.get("input_units", 0)    # expects "input_units", cascor sends "input_size"
n_hidden = topology.get("hidden_units", 0)  # matches
n_output = topology.get("output_units", 0)  # expects "output_units", cascor sends "output_size"
```

Validation guard at `network_visualizer.py:351`:

```python
if not topology_data or topology_data.get("input_units", 0) == 0:
    # Display empty graph
```

Since cascor returns `input_size` (not `input_units`), this always evaluates to 0 -- empty graph.

**Contrast**: Demo mode at `demo_backend.py:129-169` produces the graph-oriented format with
`input_units`, `output_units`, `hidden_units` (int count), `connections`, and `nodes` -- which
is why demo mode topology works.

**Impact**: Input and output node counts resolve to 0. Topology validation check fails. The
topology visualization shows an empty/placeholder graph in service mode. Connection data may
still be accessible if cascor's `connections` format matches (using `from`, `to`, `weight`
sub-keys), but the graph won't render because the validation guard rejects it.

**Fix**: Add key remapping in `extract_network_topology()`:

```python
topology = self._unwrap_response(self._client.get_topology())
if isinstance(topology, dict):
    if "input_size" in topology and "input_units" not in topology:
        topology["input_units"] = topology["input_size"]
    if "output_size" in topology and "output_units" not in topology:
        topology["output_units"] = topology["output_size"]
return topology
```

---

### 5.3 RC-6 (MODERATE) -- Dataset Scatter Plot Always Empty in Service Mode

**Description**: The service backend returns dataset metadata (sample/feature counts) but
`DatasetPlotter` and `DecisionBoundary` overlay expect raw data arrays (`inputs`, `targets`).

**Evidence**:

`ServiceBackend.get_dataset()` at `service_backend.py:155-168`:

```python
raw = self._adapter.get_dataset_info()
if "train_samples" in raw or "input_features" in raw:
    return {
        "num_samples": raw.get("train_samples", 0) + raw.get("test_samples", 0),
        "num_features": raw.get("input_features", 0),
        "num_classes": raw.get("output_features", 0),
        ...
    }
```

`DatasetPlotter._create_scatter_plot()` at `dataset_plotter.py:304-305`:

```python
inputs = dataset.get("inputs", [])    # expects actual data vectors
targets = dataset.get("targets", [])  # expects actual class labels
```

CasCor's `/v1/dataset` endpoint returns metadata only, not raw training data arrays.

**Impact**: Dataset scatter plot always empty. Decision boundary data point overlay always empty.
This was acknowledged as a known limitation in Phase 1 ("cascor's `/v1/dataset` returns
metadata only, not actual data arrays -- scatter plot will be empty"), but was not re-surfaced
in Phase 2 as a remaining issue.

**Note**: This is an architectural limitation of the cascor API, not a canopy bug. Full fix
would require either adding a data export endpoint to cascor, or having canopy fetch data
directly from juniper-data service.

---

### 5.4 RC-7 (MODERATE) -- Hardcoded Localhost URLs in MetricsPanel

**Description**: Two HTTP requests in `metrics_panel.py` use hardcoded `http://localhost:8050`
instead of dynamically constructed URLs.

**Evidence** at `metrics_panel.py:1000` and `metrics_panel.py:1021`:

```python
response = requests.get("http://localhost:8050/api/network/stats", timeout=2)  # line 1000
response = requests.get("http://localhost:8050/api/state", timeout=2)          # line 1021
```

All other callbacks use `self._api_url(path)` which dynamically determines the host from
`flask.request.host`.

**Impact**: When canopy runs in Docker (bound to `0.0.0.0:8050`), behind a reverse proxy, or
on a non-standard host/port, these requests fail silently with `ConnectionError` (caught and
logged). The network stats detail panel and training state panel in the metrics component
return fallback/empty data.

**Fix**: Replace hardcoded URLs with `self._api_url("/api/network/stats")` and
`self._api_url("/api/state")`.

---

### 5.5 RC-8 (LOW) -- WebSocket Relay Broadcasts Unnormalized Field Names

**Description**: The relay loop broadcasts cascor's raw WebSocket `metrics` messages without
applying `_normalize_metric()`, while the REST polling path normalizes field names.

**Evidence** at `cascor_service_adapter.py:203-206`:

```python
async for message in stream.stream():
    msg_type = message.get("type", "")
    data = message.get("data", message)
    await websocket_manager.broadcast({"type": msg_type, "data": data})
```

CasCor's metrics messages use `loss`, `accuracy`, `validation_loss`, `validation_accuracy`.
The REST path normalizes to `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`.

**Impact**: Currently non-functional because dashboard doesn't consume WebSocket data (RC-3).
This is a latent inconsistency that becomes a bug if RC-3 is addressed in the future.

---

### 5.6 RC-9 (LOW) -- Dead Parameter Mapping: `cn_training_iterations`/`candidate_epochs`

**Description**: The canopy-to-cascor parameter map includes `cn_training_iterations` ->
`candidate_epochs`, but cascor neither returns nor accepts `candidate_epochs`.

**Evidence**:

Forward map at `cascor_service_adapter.py:364`:

```python
"cn_training_iterations": "candidate_epochs",
```

CasCor's `get_training_params()` at `lifecycle/manager.py:511-522` returns 6 keys:
`learning_rate`, `max_hidden_units`, `epochs_max`, `patience`, `candidate_pool_size`,
`correlation_threshold`. No `candidate_epochs`.

CasCor's `TrainingParamUpdateRequest` at `routes/training.py:45-54` accepts:
`learning_rate`, `candidate_learning_rate`, `correlation_threshold`, `candidate_pool_size`,
`max_hidden_units`, `epochs_max`, `patience`. No `candidate_epochs`.

**Impact**: `cn_training_iterations` always shows default/stale value. Changes are silently
dropped. Both the real cascor service and `FakeCascorClient` omit `candidate_epochs` from
their `get_training_params()` responses, so this mapping target is unreachable in all
environments.

---

### 5.7 RC-10 (LOW) -- `candidate_learning_rate` Not Mapped

**Description**: CasCor's `candidate_learning_rate` is updatable via `PATCH /v1/training/params`
but has no corresponding canopy parameter or mapping entry in `_CANOPY_TO_CASCOR_PARAM_MAP`.

**Evidence**:

CasCor's `TrainingParamUpdateRequest` at `routes/training.py:45-54` accepts `candidate_learning_rate`
as an updatable field. CasCor's `get_training_params()` at `lifecycle/manager.py:511-522`
does not currently return it, but the update path accepts it.

The forward map at `cascor_service_adapter.py:357-365` has no entry mapping any canopy
parameter to `candidate_learning_rate`:

```python
_CANOPY_TO_CASCOR_PARAM_MAP = {
    "nn_learning_rate": "learning_rate",
    "nn_max_hidden_units": "max_hidden_units",
    "nn_max_total_epochs": "epochs_max",
    "nn_growth_convergence_threshold": "patience",
    "cn_pool_size": "candidate_pool_size",
    "cn_correlation_threshold": "correlation_threshold",
    "cn_training_iterations": "candidate_epochs",
    # No entry for candidate_learning_rate
}
```

**Impact**: Users cannot view or modify candidate learning rate from the canopy dashboard.
Adding a `cn_candidate_learning_rate` -> `candidate_learning_rate` mapping would enable this.

---

### 5.8 RC-11 (INFO) -- Dual Status Normalization Produces Inconsistent Representations

**Description**: Two independent normalization paths produce different string representations
of the same cascor status.

**Path A** -- `ServiceBackend.get_status()` at `service_backend.py:107-115`: Uses `.upper()`
comparison, returns boolean flags (`is_running`, `is_paused`, etc.) plus raw `fsm_status`.

**Path B** -- Relay callback via `CascorStateSync._normalize_status()`: Returns title-case
strings (`"Started"`, `"Paused"`, `"Completed"`, etc.).

**Impact**: `training_state` (via Path B) holds `status="Started"` while `/api/status` (via
Path A) returns `is_running=True` and `fsm_status="STARTED"`. Not a functional blocker but
increases coupling fragility.

---

## 6. Complete Root Cause Registry

```bash
REQUIREMENT: Display training progress from external juniper-cascor instance
|
|-- RC-1 [CRITICAL]: Metrics format mismatch (flat vs nested keys)
|   |-- Impact: All metrics charts empty, loss/accuracy/hidden units show 0
|   |-- Blocks: Loss plot, accuracy plot, current metrics, hidden unit markers
|   |-- Fix: Transform flat metrics to nested format at service backend level
|
|-- RC-4 [HIGH]: Uppercase status not normalized in relay path
|   |-- Impact: training_state shows "Stopped" when cascor is actually running
|   |-- Blocks: Initial WebSocket state, /api/state accuracy
|   |-- Fix: Add .lower() before _normalize_status() in relay callback
|
|-- RC-5 [MODERATE]: Topology key names don't match (input_units vs input_size)
|   |-- Impact: Network visualization empty, validation guard rejects topology
|   |-- Blocks: Network graph, topology tab
|   |-- Fix: Remap keys in extract_network_topology()
|
|-- RC-2 [MODERATE]: Relay callback omits epoch, step, hidden units, learning rate
|   |-- Impact: training_state has stale data between REST polls
|   |-- Mitigated by: /api/status makes fresh REST call each poll
|   |-- Fix: Forward additional fields in relay callback
|
|-- RC-7 [MODERATE]: Hardcoded localhost URLs in MetricsPanel
|   |-- Impact: Network stats and state unavailable in Docker/proxy deployments
|   |-- Fix: Replace with _api_url() calls
|
|-- RC-6 [MODERATE]: Dataset scatter plot empty (known limitation)
|   |-- Impact: No data visualization in dataset/boundary tabs
|   |-- Fix: Requires cascor API extension or direct juniper-data integration
|
|-- RC-8 [LOW]: WebSocket relay broadcasts raw cascor field names
|   |-- Impact: Latent inconsistency (not functional until RC-3 addressed)
|   |-- Fix: Apply _normalize_metric() in relay path
|
|-- RC-9 [LOW]: Dead candidate_epochs parameter mapping
|   |-- Impact: cn_training_iterations shows stale value, writes silently dropped
|   |-- Fix: Remove dead mapping or add endpoint to cascor
|
|-- RC-10 [LOW]: candidate_learning_rate not mapped to canopy
|   |-- Impact: Cannot view/modify candidate LR from dashboard
|   |-- Fix: Add cn_candidate_learning_rate mapping
|
|-- RC-3 [LOW]: Dashboard uses HTTP polling only
|   |-- Impact: 1s latency vs real-time
|   |-- Not a functional blocker
|   |-- Fix: Future enhancement
|
|-- RC-11 [INFO]: Dual normalization paths produce different representations
|   |-- Impact: Inconsistent status strings across data paths
|   |-- Fix: Unify normalization or document the contract
```

---

## 7. What Works Correctly in Service Mode

For completeness, these data paths function correctly in the current codebase:

| Data Path                                               | Status  | Evidence                                                                                               |
|---------------------------------------------------------|---------|--------------------------------------------------------------------------------------------------------|
| **Status bar** (is_running, phase, epoch, hidden units) | Working | `ServiceBackend.get_status()` transforms nested->flat correctly via `.upper()` comparisons             |
| **Decision boundary** visualization                     | Working | `CascorServiceAdapter.get_decision_boundary()` transforms `grid_x`/`grid_y` -> `xx`/`yy`/`Z` correctly |
| **Dataset metadata** display                            | Working | `ServiceBackend.get_dataset()` maps `train_samples` -> `num_samples` correctly                         |
| **Training control** (start/stop/pause/resume/reset)    | Working | REST forwarding with proper error handling                                                             |
| **Parameter updates** (apply_params)                    | Working | `_CANOPY_TO_CASCOR_PARAM_MAP` correctly maps 6 of 7 canopy->cascor names                               |
| **WebSocket relay** (broadcasting to browser)           | Working | Messages correctly relayed and broadcast (though with raw field names)                                 |
| **Initial state sync** (status, phase, epoch, params)   | Working | `CascorStateSync.sync()` handles both formats with `.lower()`                                          |
| **ResponseEnvelope unwrapping**                         | Working | All Phase 1 fixes correctly implemented                                                                |

---

## 8. Recommended Fix Strategy

### 8.1 Fix Priority Order

Fixes should be applied in this order. Each fix is independently testable.

| Priority | Root Cause                                     | Effort  | Risk     |
|----------|------------------------------------------------|---------|----------|
| 1        | RC-1: Metrics format mismatch                  | Small   | Low      |
| 2        | RC-4: Uppercase status in relay                | Trivial | None     |
| 3        | RC-5: Topology key names                       | Small   | Low      |
| 4        | RC-2: Relay callback field omission            | Small   | Low      |
| 5        | RC-7: Hardcoded localhost URLs                 | Trivial | None     |
| 6        | RC-9: Dead parameter mapping                   | Small   | Low      |
| 7        | RC-10: Missing candidate_learning_rate mapping | Trivial | None     |
| 8        | RC-8: Relay metric normalization               | Small   | Low      |
| 9        | RC-11: Dual normalization consistency          | Medium  | Moderate |
| 10       | RC-6: Dataset data arrays                      | Large   | Moderate |
| 11       | RC-3: WebSocket consumption                    | Large   | Moderate |

### 8.2 RC-1 Fix: Add `_to_dashboard_metric()` Transformation

Add a single transformation function in the service backend that restructures flat normalized
metrics into the nested format the dashboard expects:

```python
@staticmethod
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

Apply in `ServiceBackend.get_metrics_history()` and `ServiceBackend.get_metrics()`.

**Advantages**:

- Single-point change, no modifications to MetricsPanel or demo mode
- Preserves backward compatibility with demo mode's format
- Preserves Phase 1 normalization boundary (flat canonical form remains the adapter's contract)

**Disadvantages**:

- Adds a second transformation layer (cascor raw -> flat canonical -> nested dashboard)

### 8.3 RC-4 Fix: Lowercase Before `_normalize_status()`

At `cascor_service_adapter.py:222`, change:

```python
status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
```

To:

```python
raw = data.get("status", data.get("state", ""))
status = CascorStateSync._normalize_status(raw.lower() if isinstance(raw, str) else "")
```

### 8.4 RC-5 Fix: Topology Key Remapping

In `extract_network_topology()`, add key remapping after unwrapping:

```python
topology = self._unwrap_response(self._client.get_topology())
if isinstance(topology, dict):
    if "input_size" in topology and "input_units" not in topology:
        topology["input_units"] = topology["input_size"]
    if "output_size" in topology and "output_units" not in topology:
        topology["output_units"] = topology["output_size"]
return topology
```

### 8.5 RC-2 Fix: Forward Additional Fields in Relay Callback

At `cascor_service_adapter.py:223`, expand the callback invocation:

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

`TrainingState.update_state()` already accepts `**kwargs` and ignores `None` values.

### 8.6 RC-7 Fix: Replace Hardcoded URLs

At `metrics_panel.py:1000` and `1021`, replace:

```python
requests.get("http://localhost:8050/api/network/stats", timeout=2)
requests.get("http://localhost:8050/api/state", timeout=2)
```

With:

```python
requests.get(self._api_url("/api/network/stats"), timeout=2)
requests.get(self._api_url("/api/state"), timeout=2)
```

---

## 9. Risk Assessment

| Risk                                                          | Likelihood | Impact | Mitigation                                                                  |
|---------------------------------------------------------------|------------|--------|-----------------------------------------------------------------------------|
| RC-1 fix breaks demo mode                                     | Low        | High   | Both modes should produce identical nested format; test both paths          |
| RC-5 topology key remap misses structural differences         | Medium     | Medium | Verify cascor topology `connections` format matches visualizer expectations |
| Multiple simultaneous fixes introduce regressions             | Medium     | Medium | Fix and test one root cause at a time, in priority order                    |
| FakeCascorClient divergence masks new issues                  | High       | Medium | Add integration test gated by `CASCOR_BACKEND_AVAILABLE=1`                  |
| Relay callback changes cause unexpected TrainingState updates | Low        | Low    | `update_state()` ignores None values; verify with unit tests                |

---

## 10. Guardrails

1. **Test with real cascor**: Every fix must be verified against a running cascor instance,
   not just `FakeCascorClient`. The fake client has masked format issues repeatedly across
   both Phase 1 and Phase 2.

2. **Preserve demo mode**: All changes must be verified to not regress demo mode functionality.

3. **Single normalization boundary**: All cascor-to-canopy format transformations should pass
   through `ServiceBackend` or `CascorServiceAdapter`. Avoid adding normalization in `main.py`.

4. **Define data contracts explicitly**: The root cause of this entire issue chain is that
   `BackendProtocol` returns `Dict[str, Any]` without defining response schemas. Consider
   adding TypedDict or dataclass contracts.

5. **FakeCascorClient fidelity**: After fixing real issues, update `FakeCascorClient` to match.
   Add contract tests asserting fake client response keys match real service response keys.

---

## 11. Verification Plan

After applying fixes for RC-1, RC-4, RC-5:

### 11.1 Automated Tests

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
pytest tests/ -v
pytest tests/unit/test_response_normalization.py -v
pytest tests/regression/ -v
```

### 11.2 Manual Integration Test

1. Start juniper-data, juniper-cascor, juniper-canopy (service mode)
2. Start training on cascor
3. Verify via curl:

```bash
# Metrics format (RC-1)
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, "phase": "...", ...}]}

# Topology format (RC-5)
curl -s http://localhost:8050/api/topology | python3 -m json.tool
# Expected: {"input_units": 2, "output_units": 1, "hidden_units": N, "connections": [...]}

# Status (should already work)
curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

1. Visual verification in browser at `http://localhost:8050/dashboard/`:
   - Loss chart: non-zero training loss curve
   - Accuracy chart: non-zero accuracy curve
   - Hidden units: actual count (not always 0)
   - Network graph: input/hidden/output nodes with connections
   - Status bar: correct status, epoch, phase

---

## 12. Files Requiring Modification (Summary)

| File                                       | Root Causes            | Changes                                                                                         |
|--------------------------------------------|------------------------|-------------------------------------------------------------------------------------------------|
| `src/backend/service_backend.py`           | RC-1                   | Add `_to_dashboard_metric()`, apply in `get_metrics_history()` and `get_metrics()`              |
| `src/backend/cascor_service_adapter.py`    | RC-2, RC-4, RC-5, RC-8 | Fix relay callback (status casing, additional fields, metric normalization), topology key remap |
| `src/frontend/components/metrics_panel.py` | RC-7                   | Replace 2 hardcoded localhost URLs                                                              |
| `src/backend/cascor_service_adapter.py`    | RC-9, RC-10            | Fix parameter map entries                                                                       |

**Files NOT requiring modification**:

- `state_sync.py` -- sync path works correctly (`.lower()` already applied)
- `metrics_panel.py` -- for RC-1, fix is in backend, not the panel
- `dashboard_manager.py` -- callbacks are correct; data they receive is wrong
- `demo_mode.py` -- demo format is the target format
- `juniper-cascor` -- no server-side changes needed for these root causes

---

## 13. Conclusion

Phase 2 correctly identified the most critical blocker (RC-1, metrics format mismatch) and
accurately diagnosed the WebSocket relay limitations (RC-2, RC-3). However, the analysis
scope was too narrow -- it focused on the metrics display path and did not examine the
topology, deployment, parameter mapping, or status normalization paths.

This comprehensive analysis identified **8 additional root causes** across 4 severity levels.
Of these, **RC-4 (uppercase status in relay)** is trivial to fix but causes incorrect state
display. **RC-5 (topology key names)** prevents topology visualization entirely. **RC-7
(hardcoded URLs)** breaks deployments outside localhost.

The fundamental architectural issue underlying all root causes is the absence of explicit data
contracts between backend and frontend. `BackendProtocol` returns `Dict[str, Any]` for all
methods, allowing demo mode and service mode to silently diverge in output formats. This
divergence was invisible until the service backend was tested against a real cascor instance.

**Recommended immediate actions (in order)**:

1. Fix RC-1 -- unblocks metrics charts
2. Fix RC-4 -- trivial, eliminates incorrect state display
3. Fix RC-5 -- enables topology visualization
4. Fix RC-7 -- trivial, enables non-localhost deployment
5. Fix RC-2 -- improves state freshness
6. Run end-to-end validation against a real cascor instance
