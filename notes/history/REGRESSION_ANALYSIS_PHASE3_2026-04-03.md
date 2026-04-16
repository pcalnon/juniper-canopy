# Juniper Project: Phase 3 Regression Analysis

**Date**: 2026-04-03
**Version**: 1.0.0
**Status**: Active
**Scope**: juniper-cascor, juniper-canopy
**Author**: Claude Code (Regression Analysis)
**Supersedes**: Extends CONSOLIDATED_REGRESSION_ANALYSIS.md (Phase 1-2)

---

## Executive Summary

Four critical regressions remain after Phase 1-2 remediation (30/32 tasks resolved in CONSOLIDATED_DEVELOPMENT_ROADMAP.md). This analysis identifies root causes, evidence, and impact for each.

---

## Issue 1: Training Stalls Before Target Accuracy/Loss

### Severity: P0 — Critical (blocks all development)

### Root Cause

**RC-PHASE3-001: Missing convergence threshold in patience check**

The `check_patience()` method in `cascade_correlation.py:4449` previously used:

```python
if value_loss < best_value_loss:  # ANY improvement resets counter
```

This means even infinitesimal improvements (e.g., 1e-8 reduction in loss) reset the patience counter to zero, preventing early stopping from ever triggering. Training enters a plateau where loss decreases by negligible amounts each epoch but never triggers the patience limit.

**RC-PHASE3-002: Missing convergence threshold in candidate early stopping**

The `CandidateUnit.train()` method in `candidate_unit.py:602` previously used:

```python
if current_abs_correlation > abs(best_correlation_so_far):  # ANY improvement
```

Same issue: candidates train for maximum epochs even when correlation plateaus, wasting compute and delaying network growth.

### Evidence

1. **Code inspection**: `cascade_correlation.py:4449` — `check_patience` compared with strict `<` instead of `< best - threshold`
2. **Code inspection**: `candidate_unit.py:602` — candidate early stopping used strict `>` without threshold margin
3. **Symptom**: Training runs to `epochs_max` without convergence because patience counter never accumulates
4. **Constants**: No `_PROJECT_MODEL_CONVERGENCE_THRESHOLD` or `_PROJECT_MODEL_CANDIDATE_CONVERGENCE_THRESHOLD` constants existed

### Impact

- Training runs indefinitely or until max_epochs without reaching target accuracy
- Renders the entire platform unusable for research
- All downstream canopy monitoring shows perpetual "Training" state

### Fix Applied

1. Added `convergence_threshold = 0.001` to `CascadeCorrelationNetwork` and `CandidateUnit`
2. Changed `check_patience` to: `if value_loss < best_value_loss - self.convergence_threshold`
3. Changed candidate early stopping to: `if current_abs_correlation > abs(best_correlation_so_far) + self.convergence_threshold`
4. Added new constants: `_PROJECT_MODEL_CONVERGENCE_THRESHOLD`, `_PROJECT_MODEL_CANDIDATE_CONVERGENCE_THRESHOLD`
5. Exposed parameters through API model (`TrainingParamUpdateRequest`), lifecycle manager, config, and canopy UI

### Files Modified

| File | Repository | Change |
|------|-----------|--------|
| `cascade_correlation.py` | cascor | Convergence threshold in patience check, new attribute |
| `candidate_unit.py` | cascor | Convergence threshold in early stopping check |
| `constants_model.py` | cascor | New threshold constants (0.001) |
| `constants.py` | cascor | Constant propagation chain |
| `cascade_correlation_config.py` | cascor | Config params for convergence/candidate thresholds |
| `spiral_problem.py` | cascor | Pass convergence_threshold to config |
| `api/lifecycle/manager.py` | cascor | get_training_params() and update_params() support |
| `api/models/training.py` | cascor | Pydantic model fields for API |

---

## Issue 2: Epoch/Iteration Semantic Errors in Canopy Display

### Severity: P1 — High (renders monitoring unusable)

### Root Cause

**RC-PHASE3-003: Conflation of epoch and iteration counters**

The dashboard uses "Epoch" terminology throughout without distinguishing:

- **Epoch**: A single pass through the training data (output training step)
- **Iteration**: One complete candidate node addition + network output retraining cycle (associated with network growth)

### Evidence

1. `metrics_panel.py:1655,1767` — X-axis labels on loss/accuracy plots say "Epoch" without noting iteration boundaries
2. `demo_mode.py:1008` — `iterations=self.current_epoch * 10` conflates iterations with epochs (should use `len(self.network.hidden_units)`)
3. `dashboard_manager.py:463` — Status bar shows "Hidden Units" instead of "Iteration"
4. Network info panel lacks "Current Iteration" display

### Impact

- Users cannot distinguish training phases from cascade growth cycles
- Monitoring becomes confusing and uninterpretable
- The vertical lines "+Unit #N" on plots are the only iteration markers but aren't labeled as such

### Fixes Applied

1. `metrics_panel.py`: X-axis labels updated to "Epoch (vertical lines = iteration boundaries)"
2. `demo_mode.py:1008`: Changed `iterations=self.current_epoch * 10` to `iterations=len(self.network.hidden_units)`
3. `dashboard_manager.py`: Status bar label changed from "Hidden Units" to "Iteration"
4. `dashboard_manager.py`: Added "Current Iteration" display to network info panel

---

## Issue 3: Data and Boundary Plot Card Heights Too Small

### Severity: P2 — Medium

### Root Cause

**RC-PHASE3-004: Hardcoded plot heights too small for effective visualization**

Both the decision boundary and dataset scatter plots used `height: 600px` with `maxWidth: 700px`, which is too small for detailed inspection of training data patterns and decision boundaries.

### Evidence

1. `decision_boundary.py:150` — `style={"height": "600px", "maxWidth": "700px"}`
2. `dataset_plotter.py:222` — `style={"height": "600px", "maxWidth": "700px"}`
3. `dataset_plotter.py:228` — Distribution histogram: `style={"height": "25vh", "maxHeight": "350px"}`

### Fixes Applied

1. Decision boundary: increased to `height: 800px`, `maxWidth: 900px`
2. Dataset scatter: increased to `height: 800px`, `maxWidth: 900px`
3. Distribution histogram: increased to `height: 30vh`, `maxHeight: 450px`
4. Aspect ratios preserved via existing `scaleanchor: "x"`, `scaleratio: 1` settings

---

## Issue 4: Parameter Update Flakiness

### Severity: P1 — High (destroys user trust)

### Root Cause

**RC-PHASE3-005: Insufficient timeout, no retry, no verification**

The parameter apply handler in `dashboard_manager.py` used:

- 2-second timeout (too short for network latency or processing delays)
- Single attempt with no retry
- No verification that parameters were actually applied
- Returns `dash.no_update` on failure, leaving the `applied` store stale

**RC-PHASE3-006: Incomplete parameter mapping to cascor**

The `CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP` was missing:

- `nn_patience` -> `patience`
- `cn_patience` -> `candidate_patience`
- `cn_training_convergence_threshold` -> `candidate_convergence_threshold`
- `nn_growth_convergence_threshold` was incorrectly mapped to `patience` instead of `convergence_threshold`

### Evidence

1. `dashboard_manager.py:2788` — `timeout=2` (too short)
2. `dashboard_manager.py:2793` — `return dash.no_update` on failure (no retry)
3. `cascor_service_adapter.py:430` — `"nn_growth_convergence_threshold": "patience"` (wrong mapping)
4. Missing patience/convergence threshold params in mapping

### Fixes Applied

1. Increased timeout from 2s to 10s
2. Added retry logic (3 attempts) with exponential backoff for 429 rate-limit errors
3. Added post-apply verification via `/api/state` read-back
4. Fixed parameter mapping: `nn_growth_convergence_threshold` -> `convergence_threshold`
5. Added `nn_patience`, `cn_patience`, `cn_training_convergence_threshold` to mapping
6. Added patience UI controls to sidebar (nn-patience-input, cn-patience-input)
7. Added logging for skipped canopy-only params

---

## Root Cause Dependency Map

```text
RC-PHASE3-001 (convergence threshold) ─── PRIMARY ───> Training stall
RC-PHASE3-002 (candidate threshold)   ─── PRIMARY ───> Slow candidate training
RC-PHASE3-003 (epoch/iteration)       ─── DISPLAY ───> User confusion
RC-PHASE3-004 (plot heights)          ─── DISPLAY ───> Poor visualization
RC-PHASE3-005 (param timeout/retry)   ─── RELIABILITY ─> Flakey updates
RC-PHASE3-006 (param mapping)         ─── DATA FLOW ──> Wrong values applied
```

---

## Summary

| ID | Root Cause | Severity | Status |
|----|-----------|----------|--------|
| RC-PHASE3-001 | Convergence threshold missing in patience check | P0 | Fixed |
| RC-PHASE3-002 | Convergence threshold missing in candidate early stopping | P0 | Fixed |
| RC-PHASE3-003 | Epoch/iteration semantic conflation | P1 | Fixed |
| RC-PHASE3-004 | Plot heights too small | P2 | Fixed |
| RC-PHASE3-005 | Parameter apply: short timeout, no retry | P1 | Fixed |
| RC-PHASE3-006 | Parameter mapping incomplete/incorrect | P1 | Fixed |

---

*Generated 2026-04-03. This document covers Phase 3 regression analysis extending the consolidated analysis from Phase 1-2.*
