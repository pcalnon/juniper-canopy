# Juniper-Canopy Regression Remediation Plan

**Date**: 2026-04-03
**Branch**: `fix/regression-plots-params-semantics`
**Author**: Paul Calnon
**Status**: In Progress

---

## Summary

This document outlines the phased remediation plan for four regressions identified in
juniper-canopy. See `notes/analysis/REGRESSION_ANALYSIS_2026-04-03.md` for the full
root cause analysis.

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Training stall (convergence threshold misuse) | Critical | Resolved (3a6664d) |
| 2 | Epoch/iteration semantic display confusion | High | Resolved |
| 3 | Data/boundary plot cards too small | Medium | Resolved |
| 4 | Parameter update values not displayed | High | Resolved |

---

## Phase 1: Critical Path -- Training Stall (Resolved)

### Background

The demo mode training loop was using `self.convergence_threshold` (0.001) as the
minimum candidate correlation threshold, which accepted noise-level candidates that
could not meaningfully reduce error. This caused cascades of useless hidden unit
additions followed by loss plateaus.

### Remediation

**Commit 3a6664d** (2026-04-03): Changed line 1167 of `demo_mode.py`:

```python
# Before (incorrect)
min_corr = self.convergence_threshold if self.convergence_enabled else 0.0

# After (correct)
min_corr = getattr(self, "cn_correlation_threshold", TrainingConstants.MIN_CANDIDATE_CORRELATION)
```

This uses the proper `MIN_CANDIDATE_CORRELATION` (0.01) threshold, ensuring only
candidates with meaningful correlation to the residual error are installed.

### Verification

- Training loop now properly terminates when no high-quality candidates remain
- The `train_candidate_pool()` method returns `None` if no candidate meets the threshold
- The cascade growth loop exits gracefully at line 1190-1192

---

## Phase 2: Display and UX Fixes

### 2.1 Epoch/Iteration Semantic Correction

**Problem**: The "Current Epoch" card in the metrics panel displays a global emit
counter (`current_epoch`) that increments per `_emit_training_metrics()` call. This
is neither a true epoch (single pass through training data) nor a CasCor iteration
(network growth cycle).

**Fix**: Renamed the display label from "Current Epoch" to "Training Step" in two locations:

| File | Line | Change |
|------|------|--------|
| `src/frontend/components/metrics_panel.py` | 406 | `html.H5("Current Epoch")` -> `html.H5("Training Step")` |
| `src/frontend/dashboard_manager.py` | 2230 | `html.Strong("Current Epoch: ")` -> `html.Strong("Training Step: ")` |

**Rationale**: The existing "Grow Iteration" progress bar (line 457) already correctly
shows CasCor iterations. The existing "Candidate Epoch" progress bar (line 472) already
correctly shows candidate training epochs. Renaming the metric card to "Training Step"
eliminates the semantic ambiguity without breaking any data contracts.

### 2.2 Plot Card Height Increase

**Problem**: Decision boundary and dataset scatter plots use `height: 600px` with
`maxWidth: 700px`. With `scaleanchor` aspect ratio constraints, the actual rendered
plot area is constrained by the 700px width limit.

**Fix**: Increased both dimensions proportionally:

| File | Line | Before | After |
|------|------|--------|-------|
| `src/frontend/components/decision_boundary.py` | 150 | `600px / 700px` | `800px / 900px` |
| `src/frontend/components/dataset_plotter.py` | 222 | `600px / 700px` | `800px / 900px` |

**Rationale**: Both height and maxWidth must increase together due to the
`scaleanchor` constraint. The 800/900 ratio preserves the proportional relationship
while providing ~65% more plot area.

### 2.3 Parameter Update Display Fix

**Problem**: The `parameters_panel.py` component looks up parameter values using
unprefixed keys (e.g., `max_iterations`, `pool_size`), but the `applied-params-store`
contains `nn_`/`cn_`-prefixed keys (e.g., `nn_max_iterations`, `cn_pool_size`).
The `data.get(key, default)` calls always fall through to defaults.

**Fix**: Added prefix stripping in the `update_parameters_panel_store` callback in
`dashboard_manager.py` (line 1494):

```python
def update_parameters_panel_store(applied_data, active_tab):
    if not applied_data:
        return {}
    stripped = {}
    for key, value in applied_data.items():
        if key.startswith("nn_"):
            stripped[key[3:]] = value
        elif key.startswith("cn_"):
            stripped[key[3:]] = value
        else:
            stripped[key] = value
    return stripped
```

**Rationale**: This approach is minimally invasive -- it transforms the data at the
propagation boundary rather than modifying either the source (dashboard_manager's
apply callback) or the consumer (parameters_panel's lookup tables). The parameters
panel uses canonical unprefixed names, which is the correct abstraction.

---

## Phase 3: Validation

### Test Results

| Application | Tests Run | Passed | Failed | Skipped |
|-------------|-----------|--------|--------|---------|
| juniper-canopy (unit) | 3,291 | 3,291 | 0 | 0 |

All changes are backward compatible with the existing test suite.

---

## Future Considerations

1. **Synthetic validation metrics** (demo_mode.py:1263-1264): The fixed 10% inflation
   and constant-scale noise are cosmetic-only and do not affect training behavior.
   Consider replacing with scale-aware noise in a future sprint.

2. **Synchronous HTTP in apply callback** (dashboard_manager.py:2724): The `requests.post()`
   call blocks the event loop with a 2s timeout. Consider migrating to `httpx` async
   client for improved reliability under load.

3. **WebSocket broadcast completeness** (main.py:2046): Only `TrainingState` fields
   are broadcast after parameter updates. The remaining 21 of 24 parameters are only
   available via REST polling. Consider extending the broadcast payload.
