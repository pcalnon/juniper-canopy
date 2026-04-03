# Juniper Project: Regression Analysis

**Date**: 2026-04-02
**Scope**: juniper-cascor, juniper-canopy
**Status**: Active
**Severity**: Critical — blocks all releases, deployments, and future development

---

## Executive Summary

Two Juniper project applications — **juniper-cascor** and **juniper-canopy** — have experienced significant regressions affecting training execution, real-time monitoring, and UI rendering. The most critical issue is a **training failure in juniper-cascor** that occurs shortly after the first epoch begins, which cascades into most of the observed canopy monitoring failures.

This analysis identifies **7 root causes in juniper-cascor** and **19 issues in juniper-canopy**, categorized by severity and interdependency.

---

## Table of Contents

1. [Critical: CasCor Training Failure](#1-critical-cascor-training-failure)
2. [Critical: Canopy-CasCor Connection Failure](#2-critical-canopy-cascor-connection-failure)
3. [High: Canopy Tab Ordering](#3-high-canopy-tab-ordering)
4. [High: Canopy Training Metrics Issues](#4-high-canopy-training-metrics-issues)
5. [High: Canopy Candidate Metrics Issues](#5-high-canopy-candidate-metrics-issues)
6. [High: Network Topology Output Node Count](#6-high-network-topology-output-node-count)
7. [Medium: Decision Boundary Display](#7-medium-decision-boundary-display)
8. [Medium: Dataset View Issues](#8-medium-dataset-view-issues)
9. [Medium: HDF5 Snapshots Tab](#9-medium-hdf5-snapshots-tab)
10. [Medium: Cassandra Tab API Error](#10-medium-cassandra-tab-api-error)
11. [Low: Dark Mode Styling Issues](#11-low-dark-mode-styling-issues)
12. [CasCor Code Quality Issues](#12-cascor-code-quality-issues)
13. [Root Cause Dependency Map](#13-root-cause-dependency-map)

---

## 1. Critical: CasCor Training Failure

### Symptom

A running juniper-cascor instance fails shortly after beginning the first epoch. The canopy status bar shows "Failed".

### Root Cause Analysis

The training failure is caused by **multiple interacting bugs** in the training lifecycle:

#### RC-CASCOR-001: Walrus Operator Precedence Bug

**File**: `src/cascade_correlation/cascade_correlation.py:1708`

```python
# CURRENT (BUGGY):
if snapshot_path := self.create_snapshot() is not None:
    self.logger.info(f"... Created network snapshot at: {snapshot_path}")

# Python parses this as:
snapshot_path := (self.create_snapshot() is not None)
# snapshot_path = True/False (boolean), never the actual path
```

**Impact**: Snapshot path is lost. Log messages print `True` instead of actual path. Snapshot tracking becomes unreliable. While not a direct crash cause, it masks other failures and pollutes metrics.

**Evidence**: Python operator precedence rules — `:=` binds looser than `is not`.

#### RC-CASCOR-002: WebSocket broadcast_from_thread Coroutine Leak

**File**: `src/api/websocket/manager.py:89-101`

```python
def broadcast_from_thread(self, message: dict) -> None:
    if self._event_loop is None or self._event_loop.is_closed():
        return
    coro = self.broadcast(message)
    try:
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)
    except RuntimeError:
        coro.close()  # Only closed on RuntimeError!
        logger.debug("Event loop closed, cannot broadcast")
```

**Impact**: If `run_coroutine_threadsafe()` raises any exception other than `RuntimeError` (e.g., `ValueError`, `TypeError`), the coroutine is **never closed**. This creates unawaited coroutines that accumulate, cause warnings, and can exhaust resources or corrupt the event loop. During first-epoch training when broadcasts begin via monitoring callbacks, repeated failures create cascading coroutine leaks.

#### RC-CASCOR-003: Exception Handling in _run_training

**File**: `src/api/lifecycle/manager.py:533-538`

```python
except Exception as e:
    self.logger.error(f"Training failed: {e}", exc_info=True)
    # Exception is logged but NOT propagated to the state machine
    # WebSocket clients never receive a "training_failed" event
```

**Impact**: When training throws an exception in the background thread, the error is logged but the lifecycle manager's state machine is never updated to "Failed" state through proper channels. The WebSocket never broadcasts a failure event. Clients see training start but never receive proper termination.

#### RC-CASCOR-004: Drain Thread Queue Timing Race

**File**: `src/api/lifecycle/manager.py:383-401`

```python
# Line 388-394: Drain thread created & started
# Line 397: original_grow() called AFTER drain thread starts
# Queue doesn't exist until _ensure_worker_pool() inside grow_network()
```

**Impact**: The drain thread starts polling for `_persistent_progress_queue` before `grow_network()` creates it. If `_ensure_worker_pool()` fails, the queue is never created and the drain thread loops indefinitely on `stop_event.wait(timeout=0.1)`.

#### RC-CASCOR-005: SharedMemory Lifecycle Race Condition

**File**: `src/cascade_correlation/cascade_correlation.py:1825-1848`

After commit `db2f1a6` changed SharedMemory tracking from explicit `unregister()` to `track=False`, a race condition emerged:

1. Main process creates SharedMemory block
2. Worker processes attach with `track=False`
3. If main process receives an exception during candidate training, cleanup calls `shm.close_and_unlink()`
4. Workers may still be accessing the memory
5. Subsequent epochs cannot create new blocks if old ones are partially unlinked

#### RC-CASCOR-006: Undeclared Global Variable

**File**: `src/cascade_correlation/cascade_correlation.py:2923`

```python
def _train_candidate_unit(...) -> CandidateTrainingResult:
    global shared_object_dict  # NEVER DEFINED
```

**Impact**: If `_train_candidate_unit` ever accesses `shared_object_dict`, it raises `NameError`. This is dead code from an earlier design but creates crash risk.

#### RC-CASCOR-007: Duplicate ActivationWithDerivative Class

**Files**:

- `src/cascade_correlation/cascade_correlation.py:521`
- `src/candidate_unit/candidate_unit.py:140`

**Impact**: Identical class defined in two files with separate `ACTIVATION_MAP` dictionaries. If maps diverge, multiprocessing deserialization produces inconsistent activation functions — a silent data corruption risk.

### Failure Sequence (Most Likely Path)

1. POST `/v1/training/start` → `lifecycle.start_training()` spawns background thread
2. `fit()` completes initial output layer training successfully
3. `grow_network()` begins — drain thread starts, queue doesn't exist yet (RC-004)
4. First epoch calls `_execute_parallel_training()` → creates SharedMemory (RC-005)
5. Worker processes spawned for candidate training
6. If ANY error occurs during worker submission/result collection:
   - Exception propagates up through `grow_network()`
   - `monitored_grow` catch block triggers
   - `broadcast_from_thread()` tries to send error → coroutine leaks (RC-002)
   - Background thread logs error but doesn't update state machine (RC-003)
7. Training appears to hang or fail silently shortly after first epoch begins

---

## 2. Critical: Canopy-CasCor Connection Failure

### Symptom, Issue 2

Canopy health probe passes but `ServiceBackend` connection fails. Monitoring shows "Failed" status.

### Root Cause

**File**: `juniper-cascor-client/juniper_cascor_client/client.py:76`

Response key mismatch in `is_ready()`:

- Client expects: `result.get("data", {}).get("network_loaded")`
- Server returns: `result.get("details", {}).get("network_loaded")`

Every call to `is_ready()` returns `False` unconditionally, even when the server is healthy.

**Secondary cause**: `connect()` gates on `network_loaded` instead of liveness. If CasCor's auto-start hasn't completed, `network_loaded` is `False` even though the service is alive.

**Files affected**:

- `juniper-cascor-client/juniper_cascor_client/client.py:76` — key mismatch
- `juniper-canopy/src/backend/cascor_service_adapter.py:122-128` — should use `is_alive()` not `is_ready()`

---

## 3. High: Canopy Tab Ordering

### Symptom, Issue 3

Tabs appear in incorrect order.

### Current Order (from `dashboard_manager.py:1075-1134`)

| Position | Tab               | tab_id     |
|----------|-------------------|------------|
| 1        | Training Metrics  | metrics    |
| 2        | Candidate Metrics | candidates |
| 3        | Network Topology  | topology   |
| 4        | Decision Boundary | boundaries |
| 5        | Dataset View      | dataset    |
| 6        | Workers           | workers    |
| 7        | Parameters        | parameters |
| 8        | Snapshots         | snapshots  |
| 9        | Redis             | redis      |
| 10       | Cassandra         | cassandra  |
| 11       | Tutorial          | tutorial   |
| 12       | About             | about      |

### Expected Order (from requirements)

| Position | Tab               |
|----------|-------------------|
| 1        | Training Metrics  |
| 2        | Candidate Metrics |
| 3        | Network Topology  |
| 4        | Decision Boundary |
| 5        | Dataset View      |
| 6        | Workers           |
| 7        | Parameters        |
| 8        | HDF5 Snapshots    |
| 9        | Redis             |
| 10       | Cassandra         |
| 11       | Tutorial          |
| 12       | About             |

### Analysis

The current tab order (positions 1-7) matches the expected order. The label for position 8 should be "Snapshots" per the requirement to rename from "HDF5 Snapshots" to "Snapshots" — which is already done in the code. The remaining positions (9-12) also match. **The tab ordering appears correct.** If the user is seeing a different order, it may be due to a cached build or a browser rendering issue.

**However**, the requirement states the expected order as: Training Metrics, Candidate Metrics, Network Topology, Decision Boundary, Dataset View, **Workers**, **Parameters**, HDF5 Snapshots, Redis, Cassandra, Tutorial, About. The current code matches this order exactly.

---

## 4. High: Canopy Training Metrics Issues

### 4a. Candidate Epoch Progress Bar Stalls

**Root Cause**: Cascor training fails (RC-CASCOR-001 through RC-005), so no new epoch data arrives via WebSocket. The progress bar depends on `/api/status` endpoint data which stops updating when training fails.

### 4b. Network Parameters Section Shows Defaults

**Root Cause**: The sidebar Network Parameters section (`dashboard_manager.py:2620-2765`) populates from state received via `/api/status`. When cascor fails or connection is broken (Section 2), the values fall back to defaults from `TrainingConstants` in `canopy_constants.py`.

**Specific defaults displayed**:

- Learning Rate: `TrainingConstants.DEFAULT_LEARNING_RATE` (0.01)
- Max Hidden Units: `TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS` (1000)
- Other values from `canopy_constants.py` defaults

### 4c. Convergence Threshold Shows Wrong Value

**Root Cause**: The convergence threshold input (`nn_growth_convergence_threshold`) at `dashboard_manager.py:2620` is bound to state data. If the backend returns the number of epochs value in the convergence threshold field position (a field mapping error), or if the state dictionary keys are misaligned, the wrong value displays.

**Investigation needed**: Check the exact API response field mapping between cascor's `/v1/status` endpoint and canopy's state extraction logic.

### 4d. Network Information Section Shows All Zeros

**Root Cause**: `_update_network_info_handler` (`dashboard_manager.py:2183-2256`) reads from `/api/status`:

```python
Input Nodes: status.get("input_size", 0)
Output Nodes: status.get("output_size", 0)
```

When cascor training fails or connection is broken, these fields are missing from the response, defaulting to 0.

### 4e. Network Information Details All Zeros

**Root Cause**: `_create_network_info_table` (`metrics_panel.py:2047-2118`) reads from `/api/network/stats`. Same connection failure cascade as 4d.

### 4f. Training Loss Graph Incorrect

**Root Cause**: Loss data arrives via WebSocket (`window._juniper_ws_buffer`). When training fails, incomplete/corrupted data produces incorrect visualization. The graph may show partial data from the failed epoch.

### 4g. Training Accuracy Graph Empty

**Root Cause**: Accuracy metrics require completed epochs. If training fails during the first epoch, no accuracy data is generated.

### 4h. Learning Rate Mismatch

**Root Cause**: The left menu Learning Rate field shows the configured value from `canopy_constants.py`. The graph section heading shows the actual training learning rate from the last received WebSocket message. When training fails, these diverge.

---

## 5. High: Canopy Candidate Metrics Issues

### 5a. Candidate Epoch Progress Bar Stalled

**Root Cause**: Same as 4a — cascor training failure stops data flow.

### 5b. Pool Details Empty

**Root Cause**: Pool details are populated from `/api/candidates` or WebSocket candidate messages. No candidates are generated when training fails on first epoch.

### 5c. Pool Training Metrics All Zeros

**Root Cause**: Same cascade — no candidate training data produced.

### 5d. Candidate Training Loss Graph Not Populated

**Root Cause**: No candidate training loss data when training fails.

### 5e. Candidate Loss Graph White Background in Dark Mode

**Root Cause**: Plotly graphs need explicit dark mode configuration. The CSS rule at `dark_mode.css:279-291` styles the SVG container background:

```css
.dark-mode .js-plotly-plot .plotly .main-svg {
    background-color: var(--bg-card) !important;
}
```

But the graph's `paper_bgcolor` and `plot_bgcolor` properties in the Plotly figure layout may still be set to white defaults. The graph template needs to use transparent or dark backgrounds when dark mode is active.

**File**: `candidate_metrics_panel.py` — graph figure creation must set `paper_bgcolor` and `plot_bgcolor` based on dark mode state.

---

## 6. High: Network Topology Output Node Count

### Symptom, Issue 6

Network topology displays two output nodes even though settings specify one.

### Root Cause, Issue 6

**File**: `network_visualizer.py:907`

```python
output_nodes = [n for n in G.nodes() if G.nodes[n].get("layer") == "output"]
```

The topology data received via WebSocket may contain duplicate output node entries, or the node filtering logic may misidentify nodes. Possible causes:

1. **Topology data duplication**: The WebSocket topology buffer (`window._juniper_ws_topology`) may accumulate stale data across updates, causing duplicate nodes
2. **Graph reconstruction**: `_build_network_graph()` may add output nodes from both the current topology and a default template
3. **Node ID collision**: If output nodes are identified by both position and type, a reconfigured network may retain old output node entries

**Investigation needed**: Read the `_build_network_graph()` method and trace how topology WebSocket messages are processed.

---

## 7. Medium: Decision Boundary Display

### 7a. Aspect Ratio Issue

**File**: `decision_boundary.py:150`

```python
style={"height": "70vh", "maxHeight": "800px", "minHeight": "400px"}
```

The graph uses viewport-relative height (70vh) but the width fills the container. This stretches the visualization horizontally without matching the height, distorting the aspect ratio.

**Fix**: Set explicit aspect ratio via Plotly layout `scaleanchor` and `scaleratio`, or use CSS `aspect-ratio` property.

### 7b. Missing Hidden Node History Replay

**Requirement**: The decision boundary should display visualization for each previous hidden node addition, and support "replaying" the evolution from initial state to current state.

**Current state**: The component has no history store or replay mechanism. Each update overwrites the previous visualization.

---

## 8. Medium: Dataset View Issues

### 8a. Display Aspect Ratio

Same issue as 7a — width fills container without proportional height adjustment.

### 8b. Dataset Dropdown Not Populated

**File**: `dataset_plotter.py:104`

```python
options=[],  # Populated dynamically
```

The dropdown starts empty and should be populated by a callback that queries juniper-data for available generators. If the callback fails to connect to juniper-data or the response format is unexpected, the dropdown remains empty.

### 8c. Dataset Not Pre-populated

The dropdown `value=None` means no dataset is selected by default. It should be pre-populated with the current training dataset.

### 8d. Dataset Parameters Section Heading

**Requirement**: The section heading should be "Current Dataset" (not associated with a specific dataset type like "Spiral Dataset"). Fields should change dynamically based on dataset selection.

**Current state**: The sidebar config at `dashboard_manager.py:89` references `sidebar-nn-spiral-dataset`, suggesting the section is hardcoded to "Spiral Dataset".

### 8e. Generate Dataset Button Behavior

**Requirement**: After selecting a new dataset and clicking Generate:

1. Stop training
2. Display new dataset
3. Update feature distributions
4. If compatible, allow restarting training
5. If incompatible, prompt user to fix compatibility or start new training

**Current state**: The generate button exists but the full behavior chain (stop training, compatibility check, user prompt) is not implemented.

---

## 9. Medium: HDF5 Snapshots Tab

### 9a. Tab Rename

**Requirement**: Rename "HDF5 Snapshots" to "Snapshots".

**Current state**: Already renamed. Tab label at `dashboard_manager.py:1112` says "Snapshots". Panel header at `hdf5_snapshots_panel.py:110` also says "Snapshots". **This issue appears resolved.**

### 9b. Refresh Button and Status Message Position

**Requirement**: Move refresh button and status message to the "Available Snapshots" section heading.

**Current state**: Refresh button is in the main panel header (`hdf5_snapshots_panel.py:113-119`), not in the "Available Snapshots" section.

---

## 10. Medium: Cassandra Tab API Error

### Symptom, Issue 10

Error message displayed indicating API URL problem.

### Root Cause, Issue 10

**File**: `cassandra_panel.py:112-120`

```python
def _api_url(self, path: str) -> str:
    from flask import request
    origin = f"{request.scheme}://{request.host}"
    return urljoin(f"{origin}/", path.lstrip("/"))
```

This depends on Flask's `request` context, which is not always available in Dash callback contexts. When no request context exists, `RuntimeError` is raised. The fallback (`http://127.0.0.1:8050`) may be incorrect if the app runs on a different port.

**Fix**: Use the same pattern as other panels — construct URL from `settings.server.port`.

---

## 11. Low: Dark Mode Styling Issues

### 11a. Parameters Tab Tables White Background

**File**: `parameters_panel.py` — table components use `dbc.Table` with Bootstrap styling. While the CSS at `dark_mode.css:217-236` provides dark mode table rules, the `dbc.Table` component may inline white background styles that override CSS variables.

**Fix**: Add `className="table-dark"` or ensure inline styles don't override CSS custom properties.

### 11b. Tutorial Tab Tables White Background

Same issue as 11a — `dbc.Table` components in the tutorial content have inline styles that override dark mode CSS.

### 11c. Candidate Loss Graph White Background

See Section 5e above.

---

## 12. CasCor Code Quality Issues

### CQ-001: Misleading Import Alias

**File**: `cascade_correlation.py:39`

```python
import datetime as pd  # pd = pandas convention, misleading
```

### CQ-002: Duplicate Snapshot Counter Init

**File**: `cascade_correlation.py:760,779`

```python
self.snapshot_counter = 0  # Line 760
self.snapshot_counter = 0  # Line 779 (redundant)
```

### CQ-003: Exception Swallowing in _stop_workers

**File**: `cascade_correlation.py:2313-2315`

```python
except Exception as e:
    self.logger.error(f"... Failed to SIGKILL worker: {e}")
    # No re-raise
```

### CQ-004: SharedMemory Partial Creation Cleanup

**File**: `cascade_correlation.py:1825-1846`
If SharedMemory creation succeeds but metadata assignment fails, the block is in `_active_shm_blocks` but incomplete. No cleanup on exception.

---

## 13. Root Cause Dependency Map

```bash
RC-CASCOR-001 (walrus bug)
    └── Masks snapshot failures → corrupts metrics tracking

RC-CASCOR-002 (coroutine leak)
    ├── Corrupts event loop
    └── Blocks WebSocket broadcasts
        └── Canopy never receives failure notification
            ├── Status bar shows "Failed" (delayed detection)
            ├── Progress bars stall
            ├── Graphs stop updating
            └── Network info shows zeros

RC-CASCOR-003 (exception handling)
    └── State machine not updated on failure
        └── Lifecycle manager in inconsistent state
            └── Subsequent training attempts may fail

RC-CASCOR-004 (drain thread race)
    └── Drain thread blocks on missing queue
        └── CPU waste + delayed cleanup

RC-CASCOR-005 (SharedMemory race)
    └── Worker crash during first epoch
        └── Triggers RC-002 and RC-003 cascade

RC-CANOPY-001 (connection key mismatch)
    └── is_ready() always returns False
        └── All monitoring endpoints return stale/empty data
            ├── Network parameters show defaults
            ├── Network information shows zeros
            └── Convergence threshold shows wrong value

RC-CANOPY-002 (dark mode styling)
    └── Tables/graphs with white backgrounds in dark mode
        └── Affects Parameters, Tutorial, Candidate graphs
```

---

## Appendix: Files Referenced

### juniper-cascor

| File                                             | Lines            | Issue                  |
|--------------------------------------------------|------------------|------------------------|
| `src/cascade_correlation/cascade_correlation.py` | 1708             | Walrus operator bug    |
| `src/cascade_correlation/cascade_correlation.py` | 521, 140         | Duplicate class        |
| `src/cascade_correlation/cascade_correlation.py` | 2923             | Undeclared global      |
| `src/cascade_correlation/cascade_correlation.py` | 39               | Misleading import      |
| `src/cascade_correlation/cascade_correlation.py` | 760, 779         | Duplicate init         |
| `src/cascade_correlation/cascade_correlation.py` | 1825-1848        | SharedMemory lifecycle |
| `src/api/websocket/manager.py`                   | 89-101           | Coroutine leak         |
| `src/api/lifecycle/manager.py`                   | 383-401, 533-538 | Exception handling     |

### juniper-canopy

| File                                                 | Lines     | Issue            |
|------------------------------------------------------|-----------|------------------|
| `src/frontend/dashboard_manager.py`                  | 1075-1134 | Tab ordering     |
| `src/frontend/dashboard_manager.py`                  | 2045-2181 | Status bar       |
| `src/frontend/dashboard_manager.py`                  | 2183-2256 | Network info     |
| `src/frontend/dashboard_manager.py`                  | 89-178    | Sidebar config   |
| `src/frontend/components/metrics_panel.py`           | 2047-2118 | Network details  |
| `src/frontend/components/candidate_metrics_panel.py` | 136-151   | Progress bar     |
| `src/frontend/components/network_visualizer.py`      | 907       | Output nodes     |
| `src/frontend/components/decision_boundary.py`       | 150       | Display sizing   |
| `src/frontend/components/dataset_plotter.py`         | 104       | Dropdown         |
| `src/frontend/components/hdf5_snapshots_panel.py`    | 106-121   | Refresh position |
| `src/frontend/components/cassandra_panel.py`         | 99-120    | API URL          |
| `src/frontend/components/parameters_panel.py`        | 159       | Dark mode        |
| `src/frontend/components/tutorial_panel.py`          | 26-62     | Dark mode        |
| `src/frontend/assets/dark_mode.css`                  | 279-291   | Plotly styling   |

### juniper-cascor-client

| File                              | Lines | Issue        |
|-----------------------------------|-------|--------------|
| `juniper_cascor_client/client.py` | 76    | Key mismatch |

---
