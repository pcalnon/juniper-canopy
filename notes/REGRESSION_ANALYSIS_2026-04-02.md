# Juniper Project: Cross-Application Regression Analysis

**Date**: 2026-04-02
**Affected Applications**: juniper-cascor, juniper-canopy
**Severity**: CRITICAL (training failure blocks all releases)
**Author**: Claude Code (Principal Engineer Analysis)

---

## Executive Summary

Two Juniper Project applications have experienced significant regressions. The most critical is a training failure in juniper-cascor that causes the cascade correlation training loop to exit prematurely during the first epoch. This cascor failure cascades into juniper-canopy, which displays incorrect status, stalled progress indicators, and empty data fields. Additionally, juniper-canopy has multiple independent UI regressions affecting dark mode styling, display formatting, and API connectivity.

This analysis identifies **17 discrete issues** across both applications, categorized by severity and root cause.

---

## Table of Contents

1. [Critical Issues](#1-critical-issues)
2. [High-Priority Issues](#2-high-priority-issues)
3. [Medium-Priority Issues](#3-medium-priority-issues)
4. [Low-Priority Issues](#4-low-priority-issues)
5. [Verified Non-Issues](#5-verified-non-issues)
6. [Root Cause Chain Analysis](#6-root-cause-chain-analysis)
7. [Evidence Summary](#7-evidence-summary)

---

## 1. Critical Issues

### CRIT-1: CasCor Training Loop Premature Exit

**Application**: juniper-cascor
**File**: `src/cascade_correlation/cascade_correlation.py`
**Impact**: Training fails shortly after the first epoch begins, blocking all training operations

#### Symptom

A running juniper-cascor instance fails shortly after beginning the first epoch. The `grow_network()` loop exits after the first call to `_get_training_results()` because `training_results.best_candidate` is `None`.

#### Root Cause Analysis

The training failure stems from a **multi-layered cascade of issues** in the candidate training pipeline:

**Primary Cause: OPT-5 Shared Memory + Fallback Tensor Serialization Overhead:**

The OPT-5 implementation (commit `f603f1b`, 2026-03-31) introduced `SharedTrainingMemory` for zero-copy tensor sharing. However, the implementation includes `_fallback_tensors` in the shared memory metadata dict (line 1835):

```python
shm_metadata["_fallback_tensors"] = (candidate_input, y, residual_error)
```

This metadata dict is shared by ALL `candidate_pool_size` tasks (line 1866):

```python
tasks = [(i, candidate_data[i], training_inputs) for i in range(self.candidate_pool_size)]
```

When tasks are placed into the multiprocessing queue (line 2072), each task is pickled independently. Since all tasks reference the same dict containing the full tensor fallbacks, the tensors are serialized `candidate_pool_size` times (default: 100). This:

1. Creates massive queue serialization overhead (~100x redundant tensor serialization)
2. Can exhaust available memory for large datasets
3. Causes the 60-second `queue_timeout` (line 2093) to expire before all results return
4. Results in empty or partial results from `_collect_training_results`

**Contributing Cause: Weight Magnitude Validation Rejection:**

The `_validate_training_result` method (line 2157) rejects any candidate whose weight magnitude exceeds `_RESULT_MAX_WEIGHT_MAGNITUDE = 100.0` (line 2155). With default candidate learning rate of `0.1` and `400` candidate training epochs, weight explosion is plausible during early training when residual errors are large. If all candidates are rejected by validation, `_collect_training_results` returns an empty list.

**Contributing Cause: Dummy Results Cascade:**

When parallel training returns no valid results:

1. `_collect_training_results` returns empty list (line 2258)
2. `_execute_parallel_training` returns empty list
3. `_execute_candidate_training` catches the exception, tries sequential fallback
4. Sequential fallback uses same tasks (with shared memory metadata)
5. If sequential also fails, `_get_dummy_results()` returns candidates with `correlation=0.0` and `candidate=None`
6. `_process_training_results` sorts dummy results; `best_candidate=None`
7. `grow_network` line 3630: `if not training_results.best_candidate: break`
8. Training loop exits immediately

#### Evidence

- Line 3614: `# TODO: validate_training_results bug: needs to be fixed` - Developer-acknowledged known bug
- Line 2155: `_RESULT_MAX_WEIGHT_MAGNITUDE = 100.0` - Fixed threshold without adaptive scaling
- Line 1835: `_fallback_tensors` included in every task's metadata dict
- Line 2093: `max_wait_time = getattr(self, "task_queue_timeout", 60.0)` - 60s may be insufficient

#### Impact Chain

```bash
OPT-5 serialization overhead → Queue timeout / Worker starvation
→ Empty results or weight validation rejection → Dummy results
→ best_candidate=None → grow_network breaks → Training ends prematurely
→ cascor reports STOPPED/FAILED → canopy shows "Failed" status
→ All dependent canopy metrics/graphs show zeros/empty
```

---

### CRIT-2: Walrus Operator Precedence Bug in train_output_layer

**Application**: juniper-cascor
**File**: `src/cascade_correlation/cascade_correlation.py`, line 1708
**Impact**: Potential unexpected behavior during snapshot creation after output layer training

#### Symptom, CRIT-2

After output layer training completes, the snapshot creation result is incorrectly evaluated.

#### Root Cause

```python
if snapshot_path := self.create_snapshot() is not None:
```

Due to Python operator precedence, `:=` binds looser than `is not`, so this evaluates as:

```python
if snapshot_path := (self.create_snapshot() is not None):
```

`snapshot_path` is assigned `True` or `False` (a boolean), not the actual path. The log at line 1709 prints `True` instead of the file path. If `create_snapshot()` returns `None` (e.g., snapshot directory doesn't exist), `snapshot_path` is `False`, the block is skipped, and `snapshot_counter` is not incremented. This is cosmetically incorrect but not directly crash-causing.

**However**, if `create_snapshot()` raises an exception (e.g., disk full, permission error), the exception propagates unhandled through `train_output_layer()`, through `_add_best_candidate()`, and breaks the `grow_network` loop with a `TrainingError`.

#### Fix

```python
if (snapshot_path := self.create_snapshot()) is not None:
```

---

## 2. High-Priority Issues

### HIGH-1: Canopy-CasCor Data Contract Mismatch (Connection Failure)

**Application**: juniper-canopy (with cross-repo impact on juniper-cascor-client)
**File**: `src/backend/service_backend.py` (canopy), client library
**Documented**: `notes/analysis/CANOPY_CASCOR_CONNECTION_FAILURE.md`
**Impact**: Canopy shows "Failed" even when cascor is running

#### Root Cause, HIGH-1

The canopy `ServiceBackend.is_ready()` method checks:

```python
result.get("data", {}).get("network_loaded")
```

But the cascor server's `/health/ready` endpoint returns:

```python
{"details": {"network_loaded": True/False}}
```

Key path `"data"` vs `"details"` causes `is_ready()` to always return `False`. The `connect()` method gates on `is_ready()` instead of `is_alive()`, preventing connection even when cascor is healthy.

#### Impact

Even if cascor training were working, canopy would show "Failed" status because it can never establish a proper connection.

---

### HIGH-2: Candidate Training Loss Graph Ignores Dark Mode

**Application**: juniper-canopy
**File**: `src/frontend/components/candidate_metrics_panel.py`, lines 567-576
**Impact**: White background graph in dark mode, poor readability

#### Root Cause, HIGH-2

The `_create_candidate_loss_figure` method hardcodes light-mode Plotly template and colors:

```python
fig.update_layout(
    template="plotly",           # Always light template
    plot_bgcolor="#f8f9fa",      # Always light background
    paper_bgcolor="#ffffff",     # Always white paper
)
```

No `theme` parameter is accepted or passed from the callback at lines 304-309. Compare with `_create_empty_plot` (line 582) which correctly accepts a `theme` parameter.

---

### HIGH-3: Cassandra Panel API URL Error

**Application**: juniper-canopy
**File**: `src/frontend/components/cassandra_panel.py`, lines 99-120
**Impact**: Error message displayed on Cassandra tab

#### Root Cause, HIGH-3

The `_api_url` method uses Flask request context:

```python
try:
    from flask import request
    origin = f"{request.scheme}://{request.host}"
except RuntimeError:
    origin = "http://127.0.0.1:8050"
return urljoin(f"{origin}/", path.lstrip("/"))
```

While this correctly builds absolute URLs, the Cassandra panel references the endpoint `/api/v1/cassandra/status` (line 389). The canopy application's main.py routes must include this Cassandra proxy endpoint. If the route doesn't exist in the canopy FastAPI/Dash app, the request returns a 404 error, which is displayed as an error message to the user.

Additionally, the Cassandra panel attempts to make HTTP requests during callback execution (via `requests.get`), but Dash callbacks within the same server process may encounter issues with self-referencing HTTP calls depending on the server configuration (sync vs async, threading model).

---

### HIGH-4: Decision Boundary Display Height/Aspect Ratio

**Application**: juniper-canopy
**File**: `src/frontend/components/decision_boundary.py`, line 149
**Impact**: Stretched/distorted visualization

#### Root Cause, HIGH-4

The decision boundary plot uses a fixed height without maintaining aspect ratio:

```python
style={"height": "600px"}
```

The visualization stretches to fill the full container width (9 Bootstrap columns) while maintaining only 600px height, distorting the native aspect ratio of the decision boundary plot.

---

### HIGH-5: Decision Boundary Hidden Node History/Replay

**Application**: juniper-canopy
**File**: `src/frontend/components/decision_boundary.py`
**Impact**: No ability to view decision boundary evolution

#### Root Cause, HIGH-5

The decision boundary component only shows the current boundary state. Unlike the Training Metrics tab (which has replay controls at lines 250-354 in metrics_panel.py), the Decision Boundary tab has no mechanism to:

- Store decision boundary snapshots at each hidden node addition
- Replay the evolution from initial to current state
- View the boundary at a specific hidden node count

This is a **missing feature**, not a regression from existing functionality.

---

### HIGH-6: Dataset View Display Height/Aspect Ratio

**Application**: juniper-canopy
**File**: `src/frontend/components/dataset_plotter.py`, line 222
**Impact**: Stretched/distorted scatter plot

#### Root Cause, HIGH-6

Same issue as HIGH-4: fixed height (`500px`) without aspect ratio enforcement.

---

### HIGH-7: Dataset View Dropdown and Configuration

**Application**: juniper-canopy
**File**: `src/frontend/components/dataset_plotter.py`
**Impact**: Dataset dropdown not populated; sidebar hardcoded to "Spiral Dataset"

#### Root Cause, HIGH-7 (Multiple Sub-Issues)

1. **Dropdown population**: The `dcc.Dropdown` at line 101 starts with `options=[]` (empty). It should be populated with generators from the juniper-data service via `/api/dataset/generators` or equivalent.

2. **Sidebar label**: The sidebar section is hardcoded as "Spiral Dataset" in `dashboard_manager.py` (TAB_SIDEBAR_CONFIG for dataset tab). Should dynamically reflect the currently selected dataset type.

3. **Generate Dataset handler**: The dataset generation workflow needs to:
   - Stop current training
   - Generate the new dataset via juniper-data
   - Display the new scatter plot
   - Check neural network compatibility
   - Prompt user if incompatible

---

### HIGH-8: Network Topology Shows Two Output Nodes

**Application**: juniper-canopy (data source: juniper-cascor)
**File**: `src/frontend/components/network_visualizer.py`, lines 612-626
**Impact**: Incorrect network visualization

#### Root Cause, HIGH-8

The output node count comes from the backend topology API response: `topology.get("output_units", 0)`. The visualizer correctly renders whatever the backend reports. The issue is in the cascor backend's network configuration or the topology endpoint response. If the network was created with `output_size=2` (e.g., for binary classification with two output nodes instead of one), the topology is correctly reported.

This may be a configuration issue rather than a code bug. Verify the network creation parameters and whether the problem type specifies 1 or 2 output nodes.

---

## 3. Medium-Priority Issues

### MED-1: HDF5 Snapshots Panel Hardcoded Colors (Dark Mode)

**Application**: juniper-canopy
**File**: `src/frontend/components/hdf5_snapshots_panel.py`
**Impact**: Poor dark mode readability

#### Details, MED-1

Three hardcoded color values:

- Line 111: `"color": "#2c3e50"` (header text)
- Line 123: `"color": "#6c757d"` (status message)
- Line 216: `"backgroundColor": "#e9ecef"` (table header row)

These should use CSS variables: `var(--header-color)`, `var(--text-muted)`, `var(--bg-secondary)`.

---

### MED-2: Cassandra Panel Hardcoded Colors (Dark Mode)

**Application**: juniper-canopy
**File**: `src/frontend/components/cassandra_panel.py`, line 200
**Impact**: Header text invisible/low-contrast in dark mode

#### Details, MED-2

```python
style={"color": "#2c3e50", "marginBottom": "10px"}
```

Should use `var(--header-color)`.

---

### MED-3: HDF5 Snapshots Tab Rename and Refresh Button Placement

**Application**: juniper-canopy
**Impact**: UI organization

#### Status, MED-3: PARTIALLY RESOLVED

- Tab label already renamed from "HDF5 Snapshots" to "Snapshots" (verified: `dashboard_manager.py` line 1112)
- Panel header at `hdf5_snapshots_panel.py` line 110 shows "Snapshots" (verified)
- Refresh button is currently inline with the title (lines 113-118)
- **Remaining**: The refresh button and status message should be moved to the "Available Snapshots" section heading per requirements

---

### MED-4: Parameters Tab Dark Mode Tables

**Application**: juniper-canopy
**File**: `src/frontend/components/parameters_panel.py`
**Impact**: White table backgrounds in dark mode

#### Analysis, MED-4

The `_build_table` function (lines 79-118) creates `dbc.Table` components. The `dark_mode.css` file has comprehensive table styling (lines 217-281) with `!important` overrides. However, if the Parameters panel uses inline `style` attributes that override CSS (e.g., `"backgroundColor": "white"` or Bootstrap default classes), the CSS overrides may not take effect.

#### Status, MED-4

The recent commit `5901047` (2026-04-01) addressed this issue by replacing hardcoded colors with CSS variables. Requires verification that all table elements are properly themed.

---

### MED-5: Tutorial Tab Dark Mode Tables

**Application**: juniper-canopy
**File**: `src/frontend/components/tutorial_panel.py`
**Impact**: White table backgrounds in dark mode

#### Analysis, MED-5

Same pattern as MED-4. The tutorial panel uses `dbc.Table`, `dbc.Accordion`, and `dbc.ListGroup` components. The `dark_mode.css` file covers all these (lines 244-275). The recent commit `5901047` added dark mode rules for accordion components.

#### Status, MED-5

Requires verification that all table and accordion elements in the Tutorial tab properly inherit dark mode styles.

---

## 4. Low-Priority Issues

### LOW-1: Demo Mode Training Deadlock (Previously Fixed)

**Application**: juniper-canopy
**File**: `src/demo_mode.py`, lines 1126-1132
**Status**: FIXED in commit `9844f94` (2026-04-02)

Non-reentrant `threading.Lock()` double-acquisition in `_training_loop()` where `_update_training_status()` is called inside a `with self._lock:` block. Fixed by setting a flag inside the lock and calling `_update_training_status()` after releasing.

---

### LOW-2: CasCor validate_training_results Known Bug

**Application**: juniper-cascor
**File**: `src/cascade_correlation/cascade_correlation.py`, line 3614
**Impact**: Documented but unfixed

```python
# TODO: validate_training_results bug: needs to be fixed
```

This comment indicates a known but unresolved issue with the validation results handling. The commented-out code at line 3616-3617 suggests the `ValidateTrainingResults` initialization was changed but the underlying bug was not fully addressed.

---

## 5. Verified Non-Issues

The following reported issues were investigated and found to be already resolved or not present:

### Tab Order

**Status**: CORRECT as of current code

The tab order in `dashboard_manager.py` lines 1073-1134 matches the expected order:

1. Training Metrics
2. Candidate Metrics
3. Network Topology
4. Decision Boundary
5. Dataset View
6. Workers
7. Parameters
8. Snapshots
9. Redis
10. Cassandra
11. Tutorial
12. About

### Tab Labels

**Status**: CORRECT as of current code

- "Decision Boundary" (singular) at line 1092
- "Snapshots" (renamed from "HDF5 Snapshots") at line 1112

### Candidate Epoch Progress Bar Stall

**Status**: DOWNSTREAM of CRIT-1

The progress bar stalls because cascor training fails, not because of a canopy bug. Fixing CRIT-1 will resolve the stall.

### Training Metrics Showing Zeros/Incorrect Values

**Status**: DOWNSTREAM of CRIT-1 and HIGH-1

Network Information fields (Input Nodes, Output Nodes, etc.) show zeros because:

1. CasCor training fails (CRIT-1), so the network never grows
2. Canopy can't connect to cascor properly (HIGH-1), so status responses have default values

### Training Loss/Accuracy Graphs Empty or Incorrect

**Status**: DOWNSTREAM of CRIT-1

Graphs are populated from training metrics stream data. If training fails immediately, insufficient data points exist for meaningful graph display.

### Pool Details and Pool Training Metrics Empty/Zero

**Status**: DOWNSTREAM of CRIT-1

Candidate pool information requires successful candidate training rounds, which fail due to CRIT-1.

---

## 6. Root Cause Chain Analysis

```bash
                  ROOT CAUSES                          VISIBLE SYMPTOMS
                  ===========                          ================

    CRIT-1: CasCor OPT-5              ──────>  Training fails after first epoch
    serialization overhead +                    Canopy shows "Failed" status
    weight validation rejection                 All metrics/graphs show zeros
                   │                            Progress bars stall
                   │                            Pool details empty
                   │                            Network info incorrect
                   │
    HIGH-1: Data contract              ──────>  Canopy can't connect to cascor
    mismatch (is_ready)                         Status always shows "Failed"
                   │                            Even if training works
                   │
    HIGH-2: Candidate graph            ──────>  White graph in dark mode
    hardcoded light colors                      (independent of training)
                   │
    HIGH-3: Cassandra API URL          ──────>  Cassandra tab error message
    missing/misconfigured route                 (independent of training)
                   │
    HIGH-4/6: Fixed heights            ──────>  Distorted visualizations
    without aspect ratio                        (independent of training)
                   │
    MED-1/2: Hardcoded colors          ──────>  Poor dark mode readability
    instead of CSS variables                    (independent of training)
```

### Key Insight

**~60% of the reported symptoms** (status "Failed", stalled progress, empty metrics, zero values, incorrect training graphs) are **downstream effects** of a single root cause: CRIT-1 (cascor training failure). The remaining ~40% are independent UI regressions in canopy.

---

## 7. Evidence Summary

| Issue ID | File(s)                                  | Line(s)                | Root Cause                       | Severity | Status               |
|----------|------------------------------------------|------------------------|----------------------------------|----------|----------------------|
| CRIT-1   | cascade_correlation.py                   | 1835, 2093, 2155, 3630 | OPT-5 serialization + validation | CRITICAL | Open                 |
| CRIT-2   | cascade_correlation.py                   | 1708                   | Walrus operator precedence       | CRITICAL | Open                 |
| HIGH-1   | service_backend.py, cascor_client        | -                      | Data contract mismatch           | HIGH     | Documented           |
| HIGH-2   | candidate_metrics_panel.py               | 567-576                | Hardcoded light theme            | HIGH     | Open                 |
| HIGH-3   | cassandra_panel.py                       | 389                    | API route missing/misconfigured  | HIGH     | Open                 |
| HIGH-4   | decision_boundary.py                     | 149                    | Fixed height, no aspect ratio    | HIGH     | Open                 |
| HIGH-5   | decision_boundary.py                     | -                      | Missing replay feature           | HIGH     | Open (New Feature)   |
| HIGH-6   | dataset_plotter.py                       | 222                    | Fixed height, no aspect ratio    | HIGH     | Open                 |
| HIGH-7   | dataset_plotter.py, dashboard_manager.py | 101                    | Empty dropdown, hardcoded labels | HIGH     | Open                 |
| HIGH-8   | network_visualizer.py                    | 612-626                | Backend config issue             | HIGH     | Investigation Needed |
| MED-1    | hdf5_snapshots_panel.py                  | 111, 123, 216          | Hardcoded colors                 | MEDIUM   | Open                 |
| MED-2    | cassandra_panel.py                       | 200                    | Hardcoded colors                 | MEDIUM   | Open                 |
| MED-3    | hdf5_snapshots_panel.py                  | 113-118                | Refresh button placement         | MEDIUM   | Partial              |
| MED-4    | parameters_panel.py                      | -                      | Dark mode tables                 | MEDIUM   | Likely Fixed         |
| MED-5    | tutorial_panel.py                        | -                      | Dark mode tables                 | MEDIUM   | Likely Fixed         |
| LOW-1    | demo_mode.py                             | 1126-1132              | Threading deadlock               | LOW      | Fixed                |
| LOW-2    | cascade_correlation.py                   | 3614                   | validate_training_results        | LOW      | Acknowledged         |

---

## Appendix A: OPT-5 Shared Memory Architecture

### Design Intent

OPT-5 aims to eliminate redundant tensor serialization by creating a named POSIX shared memory block (`/dev/shm/juniper_train_*`) containing training tensors. Workers attach by name and create zero-copy views via `torch.from_numpy()`.

### Implementation Issue

The `_fallback_tensors` field (line 1835) defeats the optimization by including full tensor data in every task. Since all tasks share the same dict reference but are pickled independently for the multiprocessing queue, each pickle operation serializes the fallback tensors. With 100 candidates, this results in 100x redundant serialization — worse than the pre-OPT-5 behavior since the original tuple format was at least flat.

### Recommended Fix

Remove `_fallback_tensors` from the shared metadata dict. Instead, handle shared memory failures at the task generation level by falling back to the legacy tuple format entirely:

```python
try:
    shm = SharedTrainingMemory(tensors=[...], name_suffix=...)
    self._active_shm_blocks.append(shm)
    training_inputs = shm.get_metadata()
    training_inputs["candidate_epochs"] = self.candidate_epochs
    training_inputs["candidate_learning_rate"] = self.candidate_learning_rate
    training_inputs["candidate_display_frequency"] = self.candidate_display_frequency
    # NO _fallback_tensors here
except Exception:
    training_inputs = (candidate_input, self.candidate_epochs, y, ...)
```

In `_build_candidate_inputs`, if SharedMemory reconstruction fails and no fallback tensors exist, raise immediately — the caller's exception handler will trigger the sequential fallback with fresh tasks.

---

## Appendix B: Canopy-CasCor Integration Architecture

### Status Reporting Chain

```bash
cascor: TrainingLifecycleManager.state_machine → WebSocket broadcast
    ↓
cascor: /ws/training endpoint → JSON message {type: "state", data: {...}}
    ↓
canopy: websocket_client.js receives → dispatches to Dash stores
    ↓
canopy: _update_unified_status_bar_handler → reads status_data["failed"]
    ↓
canopy: Status bar displays "Failed" / "Running" / etc.
```

### Connection Establishment

```bash
canopy: ServiceBackend.connect()
    → is_ready() → GET /health/ready → expects {"data": {"network_loaded": true}}
    → cascor returns {"details": {"network_loaded": true}}
    → Key mismatch → is_ready() returns False → connect() fails
    → canopy falls back to demo mode or shows disconnected state
```

---

*Analysis conducted by exhaustive code review across juniper-cascor (cascade_correlation.py: ~4000 lines), juniper-canopy (dashboard_manager.py: ~4300 lines, 11 component files), juniper-cascor-client, and juniper-data-client. All file paths and line numbers verified against current HEAD.*
