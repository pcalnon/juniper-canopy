# Critical Regression Analysis: juniper-cascor and juniper-canopy

**Date**: 2026-04-02
**Severity**: CRITICAL (cascor training failure), HIGH (canopy UI regressions)
**Analyst**: Claude Code (Principal Engineer Investigation)
**Affected Applications**: juniper-cascor, juniper-canopy

---

## Executive Summary

Two Juniper project applications have experienced significant regressions affecting core functionality. The juniper-cascor application experiences a catastrophic training failure shortly after the first epoch begins, blocking all releases and development. The juniper-canopy monitoring dashboard exhibits multiple UI regressions spanning dark mode styling, data population, visualization accuracy, and API connectivity.

**Root Cause (cascor)**: The OPT-5 SharedMemory optimization (commit `f603f1b`, 2026-04-01) introduced four interrelated defects in the parallel candidate training pipeline.

**Root Cause (canopy)**: A combination of incomplete feature implementations, hardcoded styling values, missing callbacks, and a desynchronization bug in the demo mode network model.

---

## Part 1: juniper-cascor Training Failure

### 1.1 Symptom

A running juniper-cascor instance fails shortly after beginning the first epoch. Training does not complete even a single growth cycle.

### 1.2 Execution Path Analysis

The training path from entry to failure:

```bash
main.py:329 → sp.evaluate()
  → spiral_problem.py:1336 → network.fit(x, y, max_epochs)
    → cascade_correlation.py:1514 → train_output_layer() [initial, succeeds]
    → cascade_correlation.py:1540 → grow_network()
      → cascade_correlation.py:3614 → Epoch 0: calculate_residual_error()
      → cascade_correlation.py:3621 → _get_training_results()
        → cascade_correlation.py:3790 → train_candidates()
          → cascade_correlation.py:1736 → _prepare_candidate_input()
          → cascade_correlation.py:1740 → _generate_candidate_tasks()
            → cascade_correlation.py:1826 → OPT-5: SharedTrainingMemory created ★
          → cascade_correlation.py:1751 → _execute_candidate_training()
            → _execute_parallel_training()
              → Workers reconstruct tensors from SharedMemory
              → Workers attempt in-place operations on read-only views ★ CRASH
              → OR: Results collected, SharedMemory unlinked in finally ★ RACE
              → _validate_training_result rejects correlation > 1.0 ★ DATA LOSS
```

### 1.3 Root Causes Identified

#### RC-1 (CRITICAL): Non-Writable SharedMemory Tensor Views

**File**: `cascade_correlation.py:341-342` (SharedTrainingMemory.reconstruct_tensors)
**File**: `cascade_correlation.py:2850-2861` (_build_candidate_inputs)

**Evidence**: The `reconstruct_tensors` method creates tensors via:

```python
np_array = np.ndarray(shape=shape, dtype=np_dtype, buffer=buf[offset:offset+nbytes])
tensors.append(torch.from_numpy(np_array))
```

These tensors are zero-copy views into the shared memory buffer. They are **read-only** because the underlying numpy array backed by the shared memory buffer does not own its data. When PyTorch autograd or candidate training attempts any in-place operation (gradient accumulation, weight updates on input data, etc.), this raises:

```bash
RuntimeError: a view of a leaf Variable that requires grad is being used in an in-place operation
```

The `_build_candidate_inputs` method (line 2854) does not clone tensors after reconstruction. The sequential fallback path (line 2866) passes raw tuples that are writable. This asymmetry means parallel training crashes while sequential works.

**Severity**: CRITICAL - Causes immediate crash in first parallel training round.

#### RC-2 (CRITICAL): SharedMemory Use-After-Free Race Condition

**File**: `cascade_correlation.py:2129-2135` (_execute_parallel_training finally block)

**Evidence**: The `finally` block in `_execute_parallel_training` unconditionally unlinks all SharedMemory blocks:

```python
finally:
    for shm_block in list(self._active_shm_blocks):
        try:
            shm_block.close_and_unlink()
            self._active_shm_blocks.remove(shm_block)
```

With persistent workers (RC-4 optimization), workers are NOT stopped between rounds. If `_collect_training_results` times out before all workers complete, the `finally` block destroys the SharedMemory while workers may still be reading from it. Workers that subsequently attempt to access the unlinked `/dev/shm` block will crash with `FileNotFoundError` or segfault.

Additionally, after `close_and_unlink()`, any torch tensors that are zero-copy views of the shared memory buffer become dangling pointers.

**Severity**: CRITICAL - Causes intermittent crashes or data corruption in first epoch.

#### RC-3 (HIGH): Correlation Validation Rejects Valid Results

**File**: `cascade_correlation.py:2169` (_validate_training_result)

**Evidence**: The validation check strictly enforces:

```python
if not (0.0 <= result.correlation <= 1.0):
    return False
```

The Pearson correlation in `candidate_unit.py` computes `abs(numerator / (denominator + 1e-8))`. Floating-point arithmetic can produce values marginally above 1.0 (e.g., 1.0000000149). These are valid results that get discarded.

When enough results are discarded, `_process_training_results` falls back to dummy results with zero correlations, which fail the `correlation_threshold` check in `grow_network`, causing the growth loop to exit prematurely.

**Note**: The sequential path (`_execute_sequential_training`) does NOT validate results, so this only affects parallel execution.

**Severity**: HIGH - Can cause premature training termination even if RC-1 is fixed.

#### RC-4 (MODERATE): Walrus Operator Precedence Bug

**File**: `cascade_correlation.py:1708` (train_output_layer)

**Evidence**:

```python
if snapshot_path := self.create_snapshot() is not None:
```

Due to Python operator precedence, `is not` binds tighter than `:=`, so this parses as:

```python
if snapshot_path := (self.create_snapshot() is not None):
```

`snapshot_path` receives a boolean (`True`/`False`) instead of the actual path. This causes incorrect logging (prints `True` instead of a path) but does not crash training. However, it masks snapshot creation failures since `snapshot_path` is always truthy when `create_snapshot()` returns any non-None value.

**Severity**: MODERATE - Does not crash training but indicates code quality regression.

### 1.4 Regression Introduction

**Primary Commit**: `f603f1b` ("feat: implement OPT-5 for shared memory training tensors", 2026-04-01)

- Introduced SharedTrainingMemory class
- Changed task format from tuple to dict for parallel path
- Added SharedMemory lifecycle management in _execute_parallel_training

**Follow-up Commit**: `db2f1a6` ("fix: resolve resource tracker KeyErrors", 2026-04-02)

- Fixed resource tracker name mismatch (`/juniper_train_xyz` vs `juniper_train_xyz`)
- Changed to `track=False` parameter
- Did NOT fix the race condition, tensor writability, or validation issues

---

## Part 2: juniper-canopy UI Regressions

### 2.1 Tab Ordering

**Current Order** (dashboard_manager.py:1073-1135):

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

**Expected Order**: Training Metrics, Candidate Metrics, Network Topology, Decision Boundary, Dataset View, Workers, Parameters, HDF5 Snapshots, Redis, Cassandra, Tutorial, About

**Finding**: The tab order matches the expected order. The tab label at position 8 is "Snapshots" and the requirement states it should be renamed TO "Snapshots" (from "HDF5 Snapshots"). No change needed for ordering or label.

### 2.2 Status Bar Shows "Failed"

**File**: dashboard_manager.py:2045-2152 (_update_unified_status_bar_handler)

**Root Cause**: The status bar reflects the actual training state from the `/api/health` endpoint. When cascor training fails (due to the OPT-5 regressions in Part 1), the demo mode's state machine transitions to FAILED state, and the status bar correctly displays "Failed". This is a **downstream symptom** of the cascor training failure, not a canopy bug.

**Fix**: Resolve the cascor training failure (Part 1), and the status bar will correctly show "Running".

### 2.3 Training Metrics Tab Issues

#### 2.3.1 Network Parameters Section - Values From Defaults
**File**: dashboard_manager.py:580-620

The sidebar Neural Network parameters (Learning Rate, Max Hidden Units, etc.) are populated from `self.training_defaults` and `TrainingConstants` at layout construction time. They are static input fields, not dynamically populated from the running network. When the training backend fails, these show default values rather than actual network values.

**Root Cause**: These are configuration inputs, not status displays. They correctly show defaults. The "incorrect values" perception comes from the training failure preventing any real values from propagating.

#### 2.3.2 Convergence Threshold Shows Number of Epochs Value
**File**: dashboard_manager.py:698-709

The Convergence Threshold field (id: `nn-growth-convergence-threshold-input`) has `value=TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD` (0.001). The Number of Epochs field (id: `nn-growth-preset-epochs-input`) has `value=TrainingConstants.DEFAULT_PRESET_EPOCHS` (50).

**Root Cause**: If these appear to show the same value, it may be a callback issue. The growth trigger radio callback toggles enabled/disabled state but does not modify values. If the Convergence Threshold field displays the Epochs value, there may be an ID mismatch in the callback Output targets.

Checking the callback at dashboard_manager.py (growth trigger radio handler):

- The callback should toggle `disabled` property on the correct input IDs
- If the Output IDs are swapped, the wrong field gets updated

**Needs verification**: Must check the exact callback wiring for the growth trigger radio.

#### 2.3.3 Network Information Fields (All Zeros)
**File**: dashboard_manager.py:2183-2256 (_update_network_info_handler)

**Root Cause**: The Network Information panel calls `/api/status` which returns `input_size` and `output_size` from `network.input_size` and `network.output_size`. When training fails early or the demo backend hasn't fully initialized, these may return 0.

**Evidence**: demo_backend.py:104 returns `network.input_size if network else 0`. If `_demo.get_network()` returns None or an uninitialized network, all values are 0.

#### 2.3.4 Network Information Details (All Zeros)
**File**: dashboard_manager.py:2266-2285 (_update_network_info_details_handler)

**Root Cause**: Same as 2.3.3 - calls `/api/network/stats` which depends on a running network. When demo training fails, stats are empty/zero.

#### 2.3.5 Training Loss Graph Incorrect / Accuracy Graph Empty
**File**: metrics_panel.py (_create_loss_plot, _create_accuracy_plot)

**Root Cause**: Both graphs are driven by `/api/metrics/history`. When training fails in the first epoch, the metrics history is either empty or contains only partial data from the failed attempt. The loss graph may show a single anomalous point; the accuracy graph remains empty because accuracy is only computed during output training phases.

#### 2.3.6 Learning Rate Mismatch
**File**: dashboard_manager.py:440-448 (metrics card), dashboard_manager.py:600-609 (sidebar input)

**Root Cause**: The Learning Rate in the graph section header reads from `training-state-store.learning_rate` (fetched from API). The sidebar Learning Rate is a static input field with a default value. These are independent data sources. When training fails, the API-driven value may differ from the default input value.

### 2.4 Candidate Metrics Tab Issues

#### 2.4.1 Progress Bar Stalled
**Root Cause**: Same as status bar - downstream of cascor training failure.

#### 2.4.2 Pool Details Empty / Pool Training Metrics All Zeros
**Root Cause**: No candidate training data is generated when training fails in first epoch.

#### 2.4.3 Candidate Training Loss Graph Not Populated
**Root Cause**: No candidate metrics data available when training fails.

#### 2.4.4 Candidate Loss Graph White Background in Dark Mode
**File**: candidate_metrics_panel.py:567-576

**Root Cause**: The `_create_candidate_loss_figure` method hardcodes light-mode colors:

```python
fig.update_layout(
    template="plotly",
    plot_bgcolor="#f8f9fa",
    paper_bgcolor="#ffffff",
    ...
)
```

The `_create_empty_plot` method at line 582 correctly handles themes, but `_create_candidate_loss_figure` does not. This method never receives or checks the current theme state.

**Severity**: MEDIUM - Visual regression in dark mode.

### 2.5 Network Topology - Two Output Nodes

**File**: demo_mode.py:129-135 (output_weights setter)
**File**: demo_backend.py:159 (topology generation)

**Root Cause**: The `MockCascorNetwork` initializes with `output_size=1` (line 544), but the `output_weights` property setter (line 129-135) reconstructs the output_layer from the weight tensor shape WITHOUT updating `self.output_size`:

```python
@output_weights.setter
def output_weights(self, value):
    out_features, in_features = value.shape
    self.output_layer = torch.nn.Linear(in_features, out_features)
    # Missing: self.output_size = out_features
```

If any code path sets `output_weights` with a tensor of shape `(2, N)`, the output_layer becomes a 2-output layer while `output_size` remains 1. The topology generator at demo_backend.py:159 uses `network.output_size` to create output nodes, producing a desynchronized visualization.

**However**: If the problem is that 2 output nodes are being displayed and `output_size` is initialized to 1, the issue may be elsewhere - specifically in how the `output_layer` is reconstructed during training. Need to verify the exact output_weights tensor shape during demo training.

**Severity**: MEDIUM - Incorrect network visualization.

### 2.6 Decision Boundary Tab

#### 2.6.1 Aspect Ratio / Height
**File**: decision_boundary.py:150

Current: `style={"height": "70vh", "maxHeight": "800px", "minHeight": "400px"}`

**Root Cause**: The height is viewport-relative, which stretches the plot container to 70% of viewport height. The Plotly figure inside doesn't constrain its aspect ratio to match the actual decision boundary data (which should be square for 2D classification). The figure layout doesn't set `scaleanchor` or a fixed aspect ratio.

**Severity**: LOW-MEDIUM - Visual quality issue.

#### 2.6.2 Historical Boundary Display / Replay
**Root Cause**: Feature not implemented. The component only displays the current decision boundary. There is no history store, no per-hidden-node boundary capture, and no replay controls.

**Severity**: FEATURE GAP - New development required.

### 2.7 Dataset View Tab

#### 2.7.1 Aspect Ratio / Height
**File**: dataset_plotter.py:222

Current: `style={"height": "65vh", "maxHeight": "750px", "minHeight": "400px"}`

**Root Cause**: Same pattern as decision boundary - viewport-relative height without proper aspect ratio constraints on the Plotly figure.

**Severity**: LOW-MEDIUM - Visual quality issue.

#### 2.7.2 Dataset Dropdown Not Populated
**File**: dataset_plotter.py:102-108

**Root Cause**: The dropdown is initialized with `options=[]` and `value=None`. There is NO callback that populates this dropdown with available dataset generators from juniper-data. The dropdown is a dead UI element.

**Severity**: MEDIUM - Broken feature.

#### 2.7.3 Dataset Parameters Section Not Dynamic
**File**: dashboard_manager.py:722-728 (sidebar "Current Dataset" section)

**Root Cause**: The sidebar dataset section heading says "Current Dataset" (line 728) which is correct. However, the fields below are hardcoded for spiral datasets only. There is no dynamic field generation based on dataset type selection.

**Severity**: MEDIUM - Incomplete feature.

#### 2.7.4 Generate Dataset Button Behavior
**File**: dashboard_manager.py:1610-1613

**Root Cause**: The generate dataset flow opens a modal, collects parameters, and POSTs to `/api/dataset/generate`. However, it does not:

- Stop training before generating
- Check neural network compatibility with new dataset
- Prompt user for compatibility issues
- Handle dataset-network dimension mismatches

**Severity**: MEDIUM - Incomplete feature.

### 2.8 HDF5 Snapshots Tab

#### 2.8.1 Tab Label
**File**: dashboard_manager.py:1112

Current label: "Snapshots" - This matches the requirement to rename from "HDF5 Snapshots" to "Snapshots". **No change needed.**

#### 2.8.2 Refresh Button / Status Message Position
**File**: hdf5_snapshots_panel.py:106-125

The Refresh button and status message are in the component header div alongside the H3 title. The requirement asks them to be moved to the "Available Snapshots" section heading. Currently they are in the top-level header, not associated with a specific section.

**Severity**: LOW - Layout preference.

### 2.9 Cassandra Tab - API URL Error

**File**: cassandra_panel.py:99-120

**Root Cause**: The `_api_url` method uses Flask's `request.scheme` and `request.host` to construct URLs, which differs from how all other panels construct their URLs (using the dashboard_manager's `_api_url` method via `request` context). In Dash callback execution, the Flask request context may not be available, causing a `RuntimeError` that falls back to `http://127.0.0.1:8050`.

The issue is that the Cassandra panel constructs its OWN `_api_url` method independently instead of delegating to the dashboard manager's URL construction. If the application runs on a different port or behind a proxy, the fallback URL is wrong.

**Severity**: MEDIUM - Broken in non-default deployment configurations.

### 2.10 Parameters Tab - Dark Mode

**File**: parameters_panel.py

**Root Cause**: The parameters panel uses `dbc.Table` with Bootstrap classes. The dark_mode.css has table styling rules, but Bootstrap's `table` and `table-bordered` classes may have higher CSS specificity than the dark_mode.css overrides. Specifically, `dbc.Table(bordered=True)` generates Bootstrap classes that may include `background-color: white` with high specificity.

**Severity**: LOW-MEDIUM - Visual regression in dark mode.

### 2.11 Tutorial Tab - Dark Mode

**File**: tutorial_panel.py

**Root Cause**: Same as Parameters tab - Bootstrap table and component classes may override dark_mode.css. The "Dashboard Components" and "Parameters Reference" sections contain `dbc.Table` instances whose styling may not be fully overridden by the dark mode CSS.

**Severity**: LOW-MEDIUM - Visual regression in dark mode.

---

## Part 3: Issue Correlation Matrix

| Issue                                | Caused by Cascor Training Failure | Independent Bug |
|--------------------------------------|:---------------------------------:|:---------------:|
| Status bar "Failed"                  |                 X                 |                 |
| Training progress stalled            |                 X                 |                 |
| Network Parameters defaults          |                 X                 |                 |
| Network Info all zeros               |                 X                 |                 |
| Training loss graph incorrect        |                 X                 |                 |
| Accuracy graph empty                 |                 X                 |                 |
| Learning rate mismatch               |                 X                 |                 |
| Candidate progress stalled           |                 X                 |                 |
| Pool details empty                   |                 X                 |                 |
| Pool metrics all zeros               |                 X                 |                 |
| Candidate loss graph empty           |                 X                 |                 |
| Candidate loss white bg in dark mode |                                   |        X        |
| Two output nodes in topology         |                                   |        X        |
| Decision boundary aspect ratio       |                                   |        X        |
| Decision boundary history/replay     |                                   | X (feature gap) |
| Dataset dropdown not populated       |                                   |        X        |
| Dataset params not dynamic           |                                   | X (feature gap) |
| Generate dataset incomplete          |                                   | X (feature gap) |
| Cassandra API URL error              |                                   |        X        |
| Parameters dark mode                 |                                   |        X        |
| Tutorial dark mode                   |                                   |        X        |
| Snapshot refresh button position     |                                   |   X (layout)    |

**Key Insight**: 12 of 22 reported issues are downstream symptoms of the cascor OPT-5 training failure. Fixing the cascor training pipeline resolves the majority of canopy's apparent regressions.

---

## Part 4: Priority Assessment

### P0 - Catastrophic (Blocks All Development)

**1. Cascor RC-1**: Non-writable SharedMemory tensor views
**2. Cascor RC-2**: SharedMemory use-after-free race condition
**3. Cascor RC-3**: Correlation validation rejects valid results

### P1 - High (Broken Features)

**4. Cascor RC-4**: Walrus operator precedence bug
**5. Canopy**: Candidate loss plot dark mode theming
**6. Canopy**: Network topology output node count
**7. Canopy**: Dataset dropdown not populated
**8. Canopy**: Cassandra API URL construction

### P2 - Medium (Incomplete Features / Visual Issues)

**9.  Canopy**: Decision boundary aspect ratio
**10. Canopy**: Dataset view aspect ratio
**11. Canopy**: Parameters tab dark mode
**12. Canopy**: Tutorial tab dark mode
**13. Canopy**: Snapshot refresh button positioning

### P3 - Feature Gaps (New Development)

**14. Canopy**: Decision boundary historical display / replay
**15. Canopy**: Dynamic dataset parameters based on selection
**16. Canopy**: Generate dataset training integration

---

## Appendix A: Files Examined

### juniper-cascor

- `src/cascade_correlation/cascade_correlation.py` (5,071 lines)
- `src/main.py`
- `src/spiral_problem/spiral_problem.py`
- `src/candidate_unit/candidate_unit.py`
- `src/cascor_constants/`
- `notes/OPT5_SHARED_MEMORY_PLAN.md`
- `notes/FIX_RESOURCE_TRACKER_AND_WARNINGS.md`

### juniper-canopy

- `src/frontend/dashboard_manager.py` (2,857 lines)
- `src/frontend/components/metrics_panel.py` (2,118 lines)
- `src/frontend/components/candidate_metrics_panel.py`
- `src/frontend/components/network_visualizer.py`
- `src/frontend/components/decision_boundary.py`
- `src/frontend/components/dataset_plotter.py`
- `src/frontend/components/hdf5_snapshots_panel.py`
- `src/frontend/components/cassandra_panel.py`
- `src/frontend/components/parameters_panel.py`
- `src/frontend/components/tutorial_panel.py`
- `src/frontend/assets/dark_mode.css`
- `src/canopy_constants.py`
- `src/backend/demo_backend.py`
- `src/backend/demo_mode.py`
- `src/main.py`
