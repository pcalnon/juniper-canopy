# Regression Remediation Plan and Development Roadmap

**Date**: 2026-04-02
**Reference**: `notes/analysis/CRITICAL_REGRESSION_ANALYSIS_2026-04-02.md`
**Affected Applications**: juniper-cascor, juniper-canopy

---

## Phase 1: Critical Training Failure (P0) - juniper-cascor

**Priority**: IMMEDIATE - Blocks all releases, deployments, and development
**Estimated Scope**: 4 targeted fixes in `cascade_correlation.py`

### Step 1.1: Fix Non-Writable SharedMemory Tensor Views (RC-1)

**File**: `cascade_correlation.py` - `_build_candidate_inputs` method (line 2854)

**Approach A (Recommended): Clone tensors after reconstruction:**

```python
# In _build_candidate_inputs, after SharedTrainingMemory.reconstruct_tensors():
tensors, shm_handle = SharedTrainingMemory.reconstruct_tensors(training_inputs)
candidate_input, y, residual_error = tensors[0].clone(), tensors[1].clone(), tensors[2].clone()
```

| Aspect     | Assessment                                                                                           |
|------------|------------------------------------------------------------------------------------------------------|
| Strengths  | Simple, targeted fix; preserves zero-copy read from /dev/shm; clone is one-time per worker per round |
| Weaknesses | Adds memory allocation per worker (3 tensor clones); negates some OPT-5 memory savings               |
| Risks      | Minimal - clone() is a safe PyTorch operation                                                        |
| Guardrails | Existing test suite validates tensor operations; add specific test for writable clones               |

**Approach B: Make SharedMemory buffer writable:**

```python
# In SharedTrainingMemory.reconstruct_tensors(), copy data into owned buffer:
np_array = np.array(np.ndarray(shape=shape, dtype=np_dtype, buffer=buf[offset:offset+nbytes]))
```

| Aspect     | Assessment                                      |
|------------|-------------------------------------------------|
| Strengths  | Fix is at the source, affects all consumers     |
| Weaknesses | Defeats the zero-copy purpose of OPT-5 entirely |
| Risks      | Higher memory usage per worker                  |
| Guardrails | None needed beyond existing tests               |

**Recommendation**: Approach A - Clone in `_build_candidate_inputs` preserves the zero-copy read benefit (shared memory block is read once, efficiently, then cloned locally). The clone overhead is acceptable since each tensor is small relative to the serialization savings.

### Step 1.2: Fix SharedMemory Use-After-Free Race Condition (RC-2)

**File**: `cascade_correlation.py` - `_execute_parallel_training` finally block (line 2129-2135)

**Approach A (Recommended): Safe cleanup with clone-on-receipt:**

- Since Step 1.1 clones tensors after reconstruction, workers no longer hold references to the SharedMemory buffer after `_build_candidate_inputs` returns
- The SharedMemory can be safely unlinked after all tasks are DISPATCHED (not collected), because workers clone on receipt
- Move cleanup after result collection but keep it in the finally block for safety

**Approach B: Reference-counted SharedMemory blocks:**

- Track how many workers have attached/detached via a shared counter
- Only unlink when counter reaches zero

| Aspect     | Assessment                                                 |
|------------|------------------------------------------------------------|
| Strengths  | Precise lifecycle management                               |
| Weaknesses | Complex; adds cross-process synchronization primitive      |
| Risks      | Counter itself needs atomic operations; adds failure modes |
| Guardrails | Would need its own test suite                              |

**Recommendation**: Approach A - With clone-on-receipt (Step 1.1), the race condition is eliminated because workers don't hold SharedMemory references during training. The existing cleanup in the finally block becomes safe.

### Step 1.3: Fix Correlation Validation Bounds (RC-3)

**File**: `cascade_correlation.py:2169` (_validate_training_result)
**File**: `candidate_unit.py` (_calculate_correlation)

**Approach A (Recommended): Clamp at source:**

```python
# In candidate_unit.py _calculate_correlation:
correlation = min(1.0, abs(numerator_val / denominator_val))
```

| Aspect     | Assessment                                                       |
|------------|------------------------------------------------------------------|
| Strengths  | Fixes the root cause; all consumers get valid values             |
| Weaknesses | Masks floating-point imprecision                                 |
| Risks      | None - clamping to theoretical maximum is mathematically correct |
| Guardrails | Add assertion test that correlation is always in [0, 1]          |

**Approach B: Relax validation tolerance:**

```python
# In _validate_training_result:
if not (-0.001 <= result.correlation <= 1.001):
```

| Aspect     | Assessment                                  |
|------------|---------------------------------------------|
| Strengths  | Quick fix; doesn't change training math     |
| Weaknesses | Arbitrary tolerance; doesn't fix the source |
| Risks      | Could mask genuinely bad results            |
| Guardrails | Log a warning when clamping is applied      |

**Recommendation**: Approach A (clamp at source) combined with a warning log when clamping activates, to detect if the epsilon needs adjustment.

### Step 1.4: Fix Walrus Operator Precedence Bug (RC-4)

**File**: `cascade_correlation.py:1708`

**Fix** (single approach - no alternatives needed):

```python
# Before:
if snapshot_path := self.create_snapshot() is not None:
# After:
if (snapshot_path := self.create_snapshot()) is not None:
```

---

## Phase 2: Canopy Independent Bug Fixes (P1)

### Step 2.1: Fix Candidate Loss Plot Dark Mode Theming

**File**: `candidate_metrics_panel.py:567-576`

**Fix**: Pass theme state to `_create_candidate_loss_figure` and use conditional colors:

```python
def _create_candidate_loss_figure(self, history, theme="light"):
    is_dark = theme == "dark"
    # ... existing trace code ...
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly",
        plot_bgcolor="#242424" if is_dark else "#f8f9fa",
        paper_bgcolor="#242424" if is_dark else "#ffffff",
        font_color="#e9ecef" if is_dark else "#212529",
    )
```

The callback that invokes this method needs to pass `theme-state` store data.

### Step 2.2: Fix Network Topology Output Node Count

**File**: `demo_mode.py:129-135` (output_weights setter)

**Fix**: Update `output_size` when output_weights are set:

```python
@output_weights.setter
def output_weights(self, value):
    out_features, in_features = value.shape
    self.output_size = out_features  # Keep output_size synchronized
    self.output_layer = torch.nn.Linear(in_features, out_features)
    self.output_layer.weight.data = value
    self.output_optimizer = torch.optim.Adam(self.output_layer.parameters(), lr=self.learning_rate)
```

### Step 2.3: Populate Dataset Dropdown

**File**: `dataset_plotter.py` and `dashboard_manager.py`

**Fix**: Add a callback that fetches available generators from juniper-data and populates the dropdown. Also pre-select the current dataset.

### Step 2.4: Fix Cassandra Panel API URL

**File**: `cassandra_panel.py:99-120`

**Fix**: Replace the custom `_api_url` method with the same pattern used by other panels - use the dashboard manager's URL construction pattern.

---

## Phase 3: Visual and Layout Fixes (P2)

### Step 3.1: Decision Boundary Aspect Ratio
Add `scaleanchor="x"` to Plotly figure layout for square aspect ratio.

### Step 3.2: Dataset View Aspect Ratio
Same `scaleanchor` approach as decision boundary.

### Step 3.3: Parameters Tab Dark Mode
Add higher-specificity CSS rules for Bootstrap tables in dark mode.

### Step 3.4: Tutorial Tab Dark Mode
Same CSS fix as Parameters tab.

### Step 3.5: HDF5 Snapshots Refresh Button Positioning
Move Refresh button and status message to "Available Snapshots" section heading.

---

## Phase 4: Feature Development (P3 - Deferred)

### Step 4.1: Decision Boundary History and Replay
### Step 4.2: Dynamic Dataset Parameters
### Step 4.3: Generate Dataset Training Integration

---

## Development Roadmap Summary

| Phase   | Priority      | Items                 | Status   |
|---------|---------------|-----------------------|----------|
| Phase 1 | P0 - Critical | 4 cascor fixes        | Pending  |
| Phase 2 | P1 - High     | 4 canopy fixes        | Pending  |
| Phase 3 | P2 - Medium   | 5 visual/layout fixes | Pending  |
| Phase 4 | P3 - Feature  | 3 new features        | Deferred |

### Execution Order

1. **Phase 1** first - unblocks all cascor development and resolves 12/22 canopy symptoms
2. **Phase 2** second - fixes independent canopy bugs
3. **Phase 3** third - polishes visual presentation
4. **Phase 4** deferred - new feature development in subsequent sprints
