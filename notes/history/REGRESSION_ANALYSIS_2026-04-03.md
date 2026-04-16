# Juniper-Canopy Regression Analysis — 2026-04-03

**Scope**: Epoch/iteration semantics, plot sizing, parameter update flakiness
**Status**: Root cause analysis complete — fixes in development
**Affects**: juniper-canopy (display, parameter flow, UI)
**Author**: Claude Code (Principal Engineer analysis)

---

## Executive Summary

Four regression areas in juniper-canopy affect training monitoring, visualization quality, and parameter management. The most impactful are the **parameter mapping errors** which prevent runtime tuning of the cascor backend, and the **epoch/iteration semantic confusion** which makes training progress unintelligible.

---

## Issue 1: Epoch/Iteration Semantic Error — HIGH

### Definitions (Per User Specification)

- **Epoch**: A single pass through the training data (one SGD step over all samples)
- **Iteration**: One complete cascade cycle = candidate training + candidate installation + output retraining. Each iteration is associated with network growth.

### Current Behavior

In `demo_mode.py`, `current_epoch` is incremented every time `_emit_training_metrics()` is called (line 1267). This method is called:

- Multiple times during Phase 1 output training (every N steps)
- Multiple times during Phase 2 candidate training (periodically)
- At cascade boundaries
- Multiple times during Phase 2 output retraining (every N steps)

This makes `current_epoch` a **metrics emission counter**, not an epoch counter or iteration counter. The metrics panel displays this as "Epoch" which is semantically incorrect.

### What's Missing

- No separate tracking of **cascade iterations** (network growth events)
- The grow_network loop in cascor uses `epoch` as its loop variable but it's actually iterating over cascade iterations, not epochs
- The metrics panel has no way to show which cascade iteration is in progress

### Fix Required

1. Rename the display of `current_epoch` to reflect what it actually counts (or fix the counting)
2. Add a separate `current_iteration` counter that increments once per cascade cycle (when a hidden unit is installed)
3. Display both epoch count and iteration count in the metrics panel
4. Each iteration should be clearly associated with a network growth event

---

## Issue 2: Data and Boundary Plot Card Heights — MEDIUM

### Current State

**Decision boundary** (`decision_boundary.py:150`):

```python
style={"height": "600px", "maxWidth": "700px", "margin": "0 auto"}
```

**Dataset plotter** (`dataset_plotter.py:222`):

```python
style={"height": "600px", "maxWidth": "700px", "margin": "0 auto"}
```

Both use a fixed 600px height. The user wants these **increased** to make the plots larger without breaking aspect ratios.

### Fix Required

- Increase height to 800px for both plots
- Maintain `maxWidth: 700px` to preserve horizontal constraint
- The Plotly layout already sets `yaxis.scaleanchor: "x"` for decision boundary (line 366), which maintains 1:1 aspect ratio within the plot area
- No CSS `aspectRatio` needed since Plotly handles it internally

---

## Issue 3: Parameter Update Flakiness — CRITICAL

### Root Causes

#### 3a: Incorrect _CANOPY_TO_CASCOR_PARAM_MAP

**File**: `backend/cascor_service_adapter.py:430`

```python
"nn_growth_convergence_threshold": "patience",  # WRONG — maps threshold to patience
```

This mapping sends the convergence threshold VALUE as the patience VALUE. Since convergence threshold is typically a small float (0.001) and patience is an integer (10+), this either:

- Fails Pydantic validation (patience requires `ge=1`, `int` type)
- Sets patience to a tiny value, causing immediate early stopping

**Fix**: Map to `convergence_threshold` (after adding it to cascor network).

#### 3b: Missing Parameters in cn_keys List

**File**: `main.py:1997-2008`

The `cn_keys` list is missing `cn_candidate_learning_rate`. This parameter is defined in the `_CANOPY_TO_CASCOR_PARAM_MAP` but is never collected from the incoming request in `api_set_params()`.

Similarly, `nn_patience` is not in the `nn_keys` list, so patience can never be set through the canopy API.

#### 3c: Missing Parameters in _CANOPY_TO_CASCOR_PARAM_MAP

The mapping is missing:

- `nn_patience` → `patience`
- `cn_training_convergence_threshold` → `candidate_convergence_threshold`
- `cn_training_iterations` → `candidate_epochs`

#### 3d: Partial TrainingState Updates

**File**: `main.py:2024-2032`

Only `learning_rate`, `max_hidden_units`, and `max_total_epochs` are forwarded to `TrainingState`. Other updated parameters are not reflected in the status display, making it appear as though updates failed.

**Fix**: Add all nn_*and cn_* params to the TrainingState update.

#### 3e: No Error Feedback to UI

When `backend.apply_params()` fails (e.g., due to validation errors), the error is logged but not returned to the user. The API returns success even when the backend rejected the update.

---

## Issue 4: Status Display Not Reflecting Updated Values — HIGH

### Root Cause

After parameter updates, the canopy status display uses `TrainingState` which is only partially updated (Issue 3d). The parameters panel reads from a `params-store` that may not be refreshed after updates.

### Fix Required

1. Update all relevant TrainingState fields after successful parameter application
2. Broadcast updated state via WebSocket after parameter changes
3. Ensure the parameters panel callback triggers on state changes

---

## Summary Table

| Issue | Component | Severity | Fix Complexity |
|-------|-----------|----------|----------------|
| Epoch/Iteration Semantics | demo_mode.py, metrics_panel.py | HIGH | Medium |
| Plot Heights | decision_boundary.py, dataset_plotter.py | MEDIUM | Simple |
| Parameter Mapping | cascor_service_adapter.py, main.py | CRITICAL | Medium |
| Status Display | main.py, parameters_panel.py | HIGH | Simple |
