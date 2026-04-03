# Juniper Project: Regression Remediation Plan

**Date**: 2026-04-02
**Reference**: `REGRESSION_ANALYSIS_2026-04-02.md`
**Affected Applications**: juniper-cascor, juniper-canopy, juniper-cascor-client
**Author**: Claude Code (Principal Engineer)

---

## Plan Overview

This plan addresses all 17 issues identified in the regression analysis. Work is organized into 4 phases based on dependency ordering and severity. Phase 1 (cascor training fix) must complete before dependent canopy fixes can be validated.

---

## Phase 1: Critical CasCor Training Fix (CRIT-1, CRIT-2)

**Priority**: P0 - Blocks all other work
**Estimated Scope**: 3 files, ~50 lines changed

### Step 1.1: Fix OPT-5 Shared Memory Fallback Strategy

**File**: `juniper-cascor/src/cascade_correlation/cascade_correlation.py`

**Approach A (Recommended): Remove _fallback_tensors from metadata dict**

Rationale: The `_fallback_tensors` key defeats the OPT-5 optimization by including full tensor data in every task. Removing it eliminates the 100x redundant serialization that causes queue timeouts.

Changes:

1. Remove line 1835: `shm_metadata["_fallback_tensors"] = (candidate_input, y, residual_error)`
2. In `_build_candidate_inputs` (line 2856-2861): When SharedMemory reconstruction fails and no fallback exists, raise the exception. The caller's exception handler in `_execute_candidate_training` will trigger sequential fallback.
3. In `_execute_candidate_training` (line 1974-1982): When parallel fails, regenerate tasks using legacy tuple format before calling `_execute_sequential_training`:

   ```python
   # Regenerate tasks without shared memory for sequential fallback
   legacy_inputs = (candidate_input, self.candidate_epochs, y, residual_error, ...)
   legacy_tasks = [(t[0], t[1], legacy_inputs) for t in tasks]
   results = self._execute_sequential_training(legacy_tasks)
   ```

**Strengths**: Clean separation of concerns. Parallel path uses SharedMemory (lightweight). Sequential fallback uses legacy tuples (reliable). No redundant data in any path.

**Weaknesses**: Requires access to original tensors in the sequential fallback path. The `_execute_candidate_training` method must retain references to the original tensor data.

**Risks**: If `_execute_candidate_training` doesn't have direct access to the original tensors, the sequential fallback can't regenerate tasks. Mitigated by passing tensors as method parameters.

**Approach B (Alternative): Lazy fallback via closure**

Instead of storing fallback tensors in the dict, use a factory function that regenerates the legacy tuple format only when needed.

**Strengths**: Avoids any data duplication.
**Weaknesses**: More complex code path. Closures can have surprising pickling behavior in multiprocessing contexts.

**Recommendation**: Approach A is simpler and more robust.

### Step 1.2: Increase Weight Magnitude Validation Threshold

**File**: `juniper-cascor/src/cascade_correlation/cascade_correlation.py`, line 2155

**Approach**: Increase `_RESULT_MAX_WEIGHT_MAGNITUDE` from `100.0` to `1000.0` or make it configurable via the config dataclass.

**Rationale**: With learning rate 0.1 and 400 epochs, weights can legitimately reach values above 100.0, especially during early training when residual errors are large. A threshold of 1000.0 provides security against truly corrupted values while allowing legitimate training to proceed.

**Alternative**: Remove the weight magnitude check entirely and rely solely on NaN/Inf checks (lines 2188-2190). The weight magnitude check was added for security (V-4 threat model) but is overly aggressive for normal training.

**Recommendation**: Increase to 1000.0 AND add a warning log (without rejection) for values between 100.0 and 1000.0 to monitor for potential issues.

### Step 1.3: Fix Walrus Operator Precedence

**File**: `juniper-cascor/src/cascade_correlation/cascade_correlation.py`, line 1708

Change:

```python
# Before:
if snapshot_path := self.create_snapshot() is not None:
# After:
if (snapshot_path := self.create_snapshot()) is not None:
```

Also wrap in try/except to prevent snapshot failures from crashing training:

```python
try:
    if (snapshot_path := self.create_snapshot()) is not None:
        self.logger.info(f"...snapshot at: {snapshot_path}")
        self.snapshot_counter += 1
except Exception as snap_err:
    self.logger.warning(f"...snapshot creation failed: {snap_err}")
```

### Step 1.4: Validate Fix

1. Run cascor unit tests: `cd src/tests && bash scripts/run_tests.bash -u`
2. Run cascor integration tests: `cd src/tests && bash scripts/run_tests.bash -i`
3. Start cascor service and verify training completes multiple epochs
4. Monitor logs for shared memory lifecycle messages

---

## Phase 2: Canopy-CasCor Connection Fix (HIGH-1)

**Priority**: P0 - Required for canopy to display correct status
**Estimated Scope**: 2-3 files across 2 repos, ~20 lines changed

### Step 2.1: Fix Data Contract Mismatch

**Option A (Client-side fix)**: Update juniper-cascor-client to handle both response formats:

```python
# In is_ready():
data = result.get("data") or result.get("details") or {}
return data.get("network_loaded", False)
```

**Option B (Server-side fix)**: Update cascor's `/health/ready` endpoint to return `{"data": {"network_loaded": ...}}` matching the client's expectations.

**Recommendation**: Option A - more resilient to future format changes.

### Step 2.2: Fix connect() to Use is_alive() Instead of is_ready()

**File**: `juniper-canopy/src/backend/service_backend.py`

Change `connect()` to gate on `is_alive()` (liveness probe) rather than `is_ready()` (readiness probe). A service can be alive but not ready (no network loaded yet), which is a valid state during startup.

### Step 2.3: Validate Fix

1. Start cascor service without training
2. Verify canopy connects successfully
3. Start training and verify status transitions: Idle -> Training -> Running

---

## Phase 3: Canopy UI Fixes (HIGH-2 through HIGH-8, MED-1 through MED-5)

**Priority**: P1 - Visual/functional regressions
**Estimated Scope**: 6-8 files, ~200 lines changed

### Step 3.1: Candidate Metrics Graph Dark Mode (HIGH-2)

**File**: `juniper-canopy/src/frontend/components/candidate_metrics_panel.py`

1. Add `theme` parameter to `_create_candidate_loss_figure()` method signature
2. Apply dark mode template when `theme == "dark"`:

   ```python
   if theme == "dark":
       fig.update_layout(
           template="plotly_dark",
           plot_bgcolor="#242424",
           paper_bgcolor="#242424",
       )
   else:
       fig.update_layout(
           template="plotly",
           plot_bgcolor="#f8f9fa",
           paper_bgcolor="#ffffff",
       )
   ```

3. Pass theme state from the callback to the figure creation method

### Step 3.2: Cassandra Panel API Fix (HIGH-3)

**File**: `juniper-canopy/src/frontend/components/cassandra_panel.py`

Two approaches:

**Option A**: Add Cassandra proxy routes to canopy's `main.py` that forward to the actual Cassandra client.
**Option B**: Use the Cassandra client directly in callbacks (no HTTP self-call).

**Recommendation**: Option B - eliminates the HTTP self-call antipattern. The `cassandra_client.py` backend module already exists; use it directly in callbacks.

### Step 3.3: Decision Boundary Aspect Ratio (HIGH-4)

**File**: `juniper-canopy/src/frontend/components/decision_boundary.py`

Replace fixed height with aspect-ratio-preserving container:

```python
style={"width": "100%", "aspectRatio": "1/1", "maxHeight": "700px"}
```

Or use Plotly's built-in `scaleanchor` for equal axes:

```python
fig.update_layout(
    yaxis=dict(scaleanchor="x", scaleratio=1),
)
```

### Step 3.4: Decision Boundary Replay Feature (HIGH-5)

**New Feature** - Add hidden node history replay:

1. Store decision boundary data at each hidden node addition in a `dcc.Store`
2. Add a slider control for selecting hidden node count (0 to current)
3. Add play/pause/step controls for animation
4. Callback updates the boundary plot based on slider position

This is the most complex change in Phase 3. Consider implementing as a separate sub-task.

### Step 3.5: Dataset View Aspect Ratio (HIGH-6)

**File**: `juniper-canopy/src/frontend/components/dataset_plotter.py`

Same approach as Step 3.3. Replace fixed 500px height with aspect-ratio-preserving layout.

### Step 3.6: Dataset View Dropdown and Configuration (HIGH-7)

**Files**: `dataset_plotter.py`, `dashboard_manager.py`

1. **Populate dropdown**: Add a callback that fetches generator list from juniper-data via the data client (`GET /v1/generators`) and populates the dropdown options
2. **Dynamic sidebar labels**: Update `TAB_SIDEBAR_CONFIG` to use the selected dataset type as the section header instead of hardcoded "Spiral Dataset"
3. **Pre-populate current dataset**: Set the dropdown default value based on the current training dataset
4. **Generate Dataset handler**: Implement the full workflow:
   - Stop training
   - Call data client to generate new dataset
   - Display new scatter plot
   - Check compatibility (feature count matches network input_size)
   - Prompt user if incompatible
   - Allow restart with compatible network

### Step 3.7: Dark Mode Hardcoded Colors (MED-1, MED-2)

**Files**: `hdf5_snapshots_panel.py`, `cassandra_panel.py`

Replace all hardcoded color values with CSS variables:

- `"#2c3e50"` -> `"var(--header-color)"`
- `"#6c757d"` -> `"var(--text-muted)"`
- `"#e9ecef"` (backgroundColor) -> `"var(--bg-secondary)"`

### Step 3.8: HDF5 Snapshots Refresh Button Placement (MED-3)

**File**: `hdf5_snapshots_panel.py`

Move the Refresh button and status message from the main title area to the "Available Snapshots" section heading.

### Step 3.9: Verify Parameters and Tutorial Dark Mode (MED-4, MED-5)

Visual verification only. If tables still show white backgrounds after recent commit `5901047`, apply the same CSS variable pattern.

### Step 3.10: Validate All UI Fixes

1. Run canopy unit tests: `cd src && pytest -m "unit and not slow" -v`
2. Start canopy in demo mode: `./demo`
3. Visual verification of each tab in both light and dark modes
4. Verify all interactive elements function correctly

---

## Phase 4: Validation, Integration Testing, and Release

**Priority**: P1 - Required before merge
**Estimated Scope**: Testing and CI only

### Step 4.1: Run Full Test Suites

1. juniper-cascor: `cd src/tests && bash scripts/run_tests.bash -v -c`
2. juniper-canopy: `cd src && pytest tests/ -v --tb=short`
3. juniper-cascor-client: `pytest tests/ -v` (if modified in Phase 2)
4. juniper-data-client: `pytest tests/ -v` (if modified)

### Step 4.2: Integration Testing

1. Start juniper-data service
2. Start juniper-cascor service
3. Start juniper-canopy
4. Verify end-to-end training flow:
   - Network creation
   - Training start
   - Multiple epoch completion
   - Live metrics display
   - Decision boundary updates
   - Snapshot save/load

### Step 4.3: Commit and Push

1. Commit changes to each affected repo's working branch
2. Push branches to remote
3. Create pull requests

### Step 4.4: Post-Merge Cleanup

1. Delete feature branches
2. Clean up worktrees
3. Update release notes

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1 | OPT-5 fix introduces new serialization bug | Fallback to legacy tuple format is well-tested |
| 1 | Weight threshold change allows corrupted results | NaN/Inf checks still active; 1000.0 is conservative |
| 2 | Client format change breaks other consumers | Use defensive coding (handle both formats) |
| 3 | Aspect ratio changes break layout on some screens | Use maxHeight constraint to prevent overflow |
| 3 | Decision boundary replay requires significant new code | Implement as separate sub-task; can ship without |
| 3 | Dataset generator integration requires running juniper-data | Graceful degradation when service unavailable |

---

## Dependencies

```text
Phase 1 (CasCor Fix) ──────> Phase 2 (Connection Fix) ──────> Phase 4 (Validation)
                       └────> Phase 3 (Canopy UI)      ──────> Phase 4 (Validation)
```

Phases 2 and 3 can execute in parallel after Phase 1 completes. Phase 4 requires all prior phases.

---

*Plan based on analysis in REGRESSION_ANALYSIS_2026-04-02.md. All file paths verified against current HEAD.*
