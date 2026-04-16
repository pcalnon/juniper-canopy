# Juniper Project: Phase 3 Regression Remediation Plan

**Date**: 2026-04-03
**Version**: 1.0.0
**Status**: Active — Implementation Complete
**Scope**: juniper-cascor, juniper-canopy
**Author**: Claude Code (Remediation Plan)

---

## Remediation Summary

| # | Issue | Approach | Risk | Status |
|---|-------|----------|------|--------|
| 1 | Training stalling (convergence threshold) | Add minimum improvement threshold to patience check | Low | Implemented |
| 2 | Epoch/iteration semantics | Update labels, fix iteration counter, add iteration display | Low | Implemented |
| 3 | Plot card heights | Increase CSS heights preserving aspect ratios | Low | Implemented |
| 4 | Parameter update flakiness | Retry logic, increased timeout, verification, mapping fixes | Low | Implemented |

---

## Remediation 1: Training Convergence Threshold

### Problem

Training stalls because patience counter resets on any improvement, no matter how small.

### Approach Selected

Add a `convergence_threshold` parameter (default: 0.001) that defines the minimum loss improvement required to reset the patience counter.

### Alternative Approaches Considered

| Approach | Strengths | Weaknesses | Risk |
|----------|-----------|------------|------|
| **A: Convergence threshold (selected)** | Simple, targeted, configurable | Requires threshold tuning | Low |
| B: Relative improvement check | Scale-invariant | More complex, harder to explain | Medium |
| C: Sliding window variance | Statistically robust | 50+ lines of new code, harder to debug | High |

### Rationale

Approach A was selected because:

- Directly addresses the root cause with minimal code change
- Configurable via API without restart (exposed through TrainingParamUpdateRequest)
- Consistent with standard early stopping implementations in ML frameworks
- Default value of 0.001 is a well-established heuristic

### Changes

**juniper-cascor:**

1. `constants_model.py`: Added `_PROJECT_MODEL_CONVERGENCE_THRESHOLD = 0.001` and `_PROJECT_MODEL_CANDIDATE_CONVERGENCE_THRESHOLD = 0.001`
2. `constants.py`: Propagated through constant chain
3. `cascade_correlation_config.py`: Added `convergence_threshold` and `candidate_patience`/`candidate_convergence_threshold` constructor params
4. `cascade_correlation.py:4449`: Changed `if value_loss < best_value_loss:` to `if value_loss < best_value_loss - self.convergence_threshold:`
5. `cascade_correlation.py:655-657`: Initialize convergence attributes from config
6. `cascade_correlation.py:1295-1297`: Pass candidate patience/convergence to CandidateUnit
7. `candidate_unit.py:602`: Changed early stopping to use `+ self.convergence_threshold`
8. `api/lifecycle/manager.py`: Added to `get_training_params()` and `update_params()`
9. `api/models/training.py`: Added Pydantic fields
10. `spiral_problem.py`: Pass convergence_threshold to config

### Risk Assessment

- **Blast radius**: Training convergence behavior changes for all training runs
- **Reversibility**: Easy — revert threshold to 0.0 to restore original behavior
- **Guardrails**: API validation constrains threshold to (0, 1.0]

---

## Remediation 2: Epoch/Iteration Semantics

### Problem

Dashboard conflates epochs (data passes) with iterations (cascade growth cycles).

### Approach

Update UI labels and data sources to clearly distinguish the two concepts:

- Epoch = single pass through training data
- Iteration = candidate node addition + output retraining cycle

### Changes

**juniper-canopy:**

1. `metrics_panel.py:1655,1767`: X-axis labels changed from "Epoch" to "Epoch (vertical lines = iteration boundaries)"
2. `demo_mode.py:1008`: Fixed `iterations=self.current_epoch * 10` to `iterations=len(self.network.hidden_units)` (actual iteration count)
3. `dashboard_manager.py:459-473`: Status bar "Hidden Units" label changed to "Iteration"
4. `dashboard_manager.py:2253-2270`: Added "Current Iteration" display to network info panel

### Risk Assessment

- **Blast radius**: Display-only changes (no algorithm impact)
- **Reversibility**: Trivial — revert labels
- **Guardrails**: Existing `+Unit #N` vertical lines already mark iteration boundaries on plots

---

## Remediation 3: Plot Card Heights

### Problem

Data and boundary plots too small for effective visualization.

### Approach

Increase CSS heights while preserving aspect ratios via existing `scaleanchor`/`scaleratio` settings.

### Changes

**juniper-canopy:**

1. `decision_boundary.py:150`: `600px` -> `800px`, `700px` maxWidth -> `900px`
2. `dataset_plotter.py:222`: `600px` -> `800px`, `700px` maxWidth -> `900px`
3. `dataset_plotter.py:228`: `25vh/350px` -> `30vh/450px` (histogram)

### Risk Assessment

- **Blast radius**: Visual only
- **Reversibility**: Trivial — revert CSS values

---

## Remediation 4: Parameter Update Reliability

### Problem

Parameter updates fail silently due to short timeout, no retry, incorrect mapping.

### Approach

Multi-layered fix: increase timeout, add retry with backoff, add verification, fix mapping.

### Alternative Approaches Considered

| Approach | Strengths | Weaknesses |
|----------|-----------|------------|
| **A: Retry + verification (selected)** | Comprehensive, user-visible feedback | Slightly more complex |
| B: Increase timeout only | Simplest change | Doesn't address mapping or verification |
| C: WebSocket-based param updates | Real-time, no polling | Major architectural change |

### Changes

**juniper-canopy:**

1. `dashboard_manager.py:2787-2807`: Apply handler rewritten with:
   - 10s timeout (was 2s)
   - 3 retries with 0.5s exponential backoff on 429 errors
   - Post-apply verification via `/api/state` read-back
   - Detailed logging per attempt
2. `cascor_service_adapter.py:430`: Fixed mapping `nn_growth_convergence_threshold` -> `convergence_threshold` (was incorrectly mapped to `patience`)
3. `cascor_service_adapter.py:431-436`: Added `nn_patience`, `cn_patience`, `cn_training_convergence_threshold` to mapping
4. `cascor_service_adapter.py:448`: Added logging for skipped canopy-only params
5. `canopy_constants.py`: Added patience constants (DEFAULT_PATIENCE=50, DEFAULT_CN_PATIENCE=30)
6. `dashboard_manager.py`: Added `nn-patience-input` and `cn-patience-input` UI controls
7. `demo_mode.py`: Added patience params to type validation dict
8. `main.py`: Added patience params to state endpoint and set_params whitelist

### Risk Assessment

- **Blast radius**: Parameter flow changes across frontend and backend
- **Reversibility**: Moderate — multiple files, but each change is isolated
- **Guardrails**: Verification step catches silent failures; retry prevents transient errors

---

## Verification Plan

### Unit Tests

```bash
# juniper-cascor
cd /path/to/cascor-worktree/src && python -m pytest tests/ -v

# juniper-canopy
cd /path/to/canopy-worktree/src && python -m pytest tests/ -v -m "not requires_cascor and not requires_server"
```

### Integration Verification

1. Start juniper-cascor, initiate training
2. Verify training progresses past initial plateau (convergence threshold enables patience to fire)
3. Verify canopy status bar shows "Iteration" count incrementing with cascade additions
4. Verify decision boundary and dataset plots are larger (800px height)
5. Apply parameter changes via sidebar — verify confirmation message and backend state match
6. Check that loss/accuracy plots show "Epoch (vertical lines = iteration boundaries)" x-axis

---

*Generated 2026-04-03. Implementation complete for all four remediations.*
