# Juniper Canopy -- Regression Analysis

**Date**: 2026-04-03
**Version**: 1.0.0
**Status**: Current
**Scope**: Four regression issues affecting juniper-canopy dashboard accuracy, display, and parameter propagation
**Branch**: `fix/regression-plots-params-semantics`

---

## Summary Table

| # | Issue | Severity | Component(s) | Status |
|---|-------|----------|---------------|--------|
| 1 | Training Stall (Cross-Application) | **Critical** | `demo_mode.py`, juniper-cascor `cascade_correlation.py` | Primary stall fixed (commit `3a6664d`). Cosmetic residual remains. |
| 2 | Epoch/Iteration Semantic Error | **High** | `metrics_panel.py` | Fixed -- renamed to "Training Step" |
| 3 | Data/Boundary Plot Card Heights | **Medium** | `decision_boundary.py`, `dataset_plotter.py` | Fixed -- increased to 800px/900px |
| 4 | Parameter Update Flakiness | **Critical** | `dashboard_manager.py`, `parameters_panel.py` | Fixed -- prefix stripping callback added |

---

## Issue 1: Training Stall (Cross-Application)

**Severity**: Critical
**Components**: `src/demo_mode.py` (canopy), `src/cascade_correlation/cascade_correlation.py` (cascor)
**Status**: Primary stall fixed. Cosmetic residual remains.

### Root Cause

The training stall was a multi-layer problem spanning both juniper-cascor and juniper-canopy.

**Primary cause (fixed)**: Commit `3a6664d` resolved the critical convergence threshold misuse in juniper-cascor. The `grow_network()` method was using the convergence threshold value (`0.001`) as the candidate correlation minimum, when it should have been using `MIN_CANDIDATE_CORRELATION` (`0.01`). This caused the network to accept near-zero-correlation candidates that contributed no useful signal, stalling the cascade growth cycle.

**Historical context**: The existing root cause document (`notes/development/ROOT_CAUSE_LOSS_HISTORY_STALL.md`) is outdated. It refers to pre-Phase 6C architecture, describing invisible retraining and loss inflation issues that were already resolved during the Phase 6C training loop refactor. The document should be updated or archived with a pointer to this analysis.

### Evidence

**Convergence threshold misuse** (cascor `cascade_correlation.py`, line 3602):

```python
elif training_results.best_candidate.get_correlation() < self.correlation_threshold:
```

Before the fix, `self.correlation_threshold` was being set from the convergence threshold configuration value (`0.001`) instead of the dedicated `MIN_CANDIDATE_CORRELATION` constant (`0.01`). This allowed candidates with near-zero correlation to be accepted and installed into the network, producing no learning progress.

### Remaining Cosmetic Issue

**Synthetic validation metrics** (`src/demo_mode.py`, lines 1263-1264):

```python
val_loss = loss * 1.1 + np.random.randn() * 0.01
val_accuracy = accuracy * 0.95 + np.random.randn() * 0.01
```

The demo mode generates synthetic validation loss and accuracy using a fixed 10% inflation factor plus constant-magnitude Gaussian noise. When the base loss is near zero, the noise term can drive `val_loss` negative. Similarly, when accuracy is near 1.0, `val_accuracy` can exceed 1.0 or dip unrealistically. This does not affect real training -- only the demo mode visualization.

### Proposed Remediation (Cosmetic)

- Clamp `val_loss` to `max(0.0, val_loss)` and `val_accuracy` to `clip(0.0, 1.0)`
- Scale the noise magnitude proportionally to the base metric value (e.g., `loss * 0.05` instead of fixed `0.01`)
- Archive or update `ROOT_CAUSE_LOSS_HISTORY_STALL.md` with a deprecation header pointing to this analysis

---

## Issue 2: Epoch/Iteration Semantic Error

**Severity**: High
**Component**: `src/frontend/components/metrics_panel.py`
**Status**: Fixed

### Root Cause

The "Current Epoch" metric card in the dashboard displayed the value of `current_epoch`, which is not a true epoch count. It is a **global emit counter** -- a monotonic integer incremented once per call to `_emit_training_metrics()` in `demo_mode.py` (line 1267):

```python
self.current_epoch += 1
```

This counter increments during both Phase 1 output training AND during cascade growth retraining. Each `_emit_training_metrics()` call represents one metrics broadcast cycle, not one pass through the training data.

The label "Current Epoch" was misleading because:

1. It does NOT represent a true epoch (a single pass through the full training dataset)
2. It does NOT represent a CasCor iteration (one complete candidate-pool-train / select / grow / retrain cycle)
3. It conflates output retraining steps with growth cycle steps into a single counter

### Evidence

The other progress indicators in `metrics_panel.py` already use correct terminology:

| Component | Line | Label | Semantic | Correct? |
|-----------|------|-------|----------|----------|
| Progress bar | 457 | "Grow Iteration" | Network growth cycle count | Yes |
| Progress bar | 472 | "Candidate Epoch" | Candidate training epoch count | Yes |
| Metric card | 406 | ~~"Current Epoch"~~ "Training Step" | Global emit counter | **Fixed** |

### Fix Applied

Renamed the metric card label from "Current Epoch" to "Training Step" at `metrics_panel.py` line 406:

```python
html.H5("Training Step"),
```

This accurately reflects the semantics: it is a monotonic step counter that increments each time metrics are emitted, regardless of which training phase is active.

---

## Issue 3: Data/Boundary Plot Card Heights

**Severity**: Medium
**Components**: `src/frontend/components/decision_boundary.py`, `src/frontend/components/dataset_plotter.py`
**Status**: Fixed

### Root Cause

Both the decision boundary plot and the dataset scatter plot used constrained CSS dimensions that limited the visible rendering area. The original values were:

```python
style={"height": "600px", "maxWidth": "700px", "margin": "0 auto"}
```

Both plots use Plotly's `scaleanchor` constraint to maintain a 1:1 aspect ratio between the X and Y axes. With this constraint active, the rendered plot area is determined by the **smaller** of the height and width dimensions. Increasing only the height (e.g., to 800px) without also increasing `maxWidth` would add vertical whitespace without expanding the actual plot, because the 700px `maxWidth` would remain the binding constraint.

### Evidence

- `decision_boundary.py` line 150: `style={"height": "800px", "maxWidth": "900px", "margin": "0 auto"}`
- `dataset_plotter.py` line 222: `style={"height": "800px", "maxWidth": "900px", "margin": "0 auto"}`

Both files now show the corrected values.

### Fix Applied

Both dimensions were increased together to maintain the aspect ratio benefit:

| Property | Before | After |
|----------|--------|-------|
| `height` | `600px` | `800px` |
| `maxWidth` | `700px` | `900px` |

This provides approximately 65% more rendered plot area while keeping the plot centered via `margin: 0 auto`.

---

## Issue 4: Parameter Update Flakiness

**Severity**: Critical
**Components**: `src/frontend/dashboard_manager.py`, `src/frontend/components/parameters_panel.py`
**Status**: Fixed

### Root Cause (Primary)

A **key name mismatch** between the `applied-params-store` and the `parameters_panel.py` lookup caused the parameters panel to always display default values instead of the user's applied configuration.

**The mismatch chain**:

1. The sidebar input components collect parameters with `nn_` and `cn_` prefixes (e.g., `nn_max_iterations`, `cn_pool_size`) -- see `dashboard_manager.py` lines 1870-1891
2. The apply callback stores these prefixed keys directly into `applied-params-store` (line 1211)
3. `parameters_panel.py` defines parameter keys WITHOUT prefixes (e.g., `max_iterations`, `pool_size`) -- see `NETWORK_TRAINING_PARAMS` at line 49 and `CANDIDATE_TRAINING_PARAMS` at line 66
4. The `_build_table()` function calls `data.get(key, default)` (line 95) to look up each parameter

Since `data.get("max_iterations", ...)` was called against a dictionary containing `nn_max_iterations`, the key was never found and `data.get()` always returned the default value. The parameters panel appeared to work but **silently showed defaults for every parameter, every time**.

### Evidence

**Parameter definitions** (`parameters_panel.py`, lines 48-76) use unprefixed keys:

```python
NETWORK_TRAINING_PARAMS = [
    ("max_iterations", "Maximum Iterations", ...),
    ("max_total_epochs", "Maximum Total Epochs", ...),
    ...
]
CANDIDATE_TRAINING_PARAMS = [
    ("pool_size", "Pool Size", ...),
    ("correlation_threshold", "Correlation Threshold", ...),
    ...
]
```

**Store data** uses prefixed keys (`dashboard_manager.py`, lines 1870-1891):

```python
nn_max_iter,
nn_max_epochs,
...
cn_pool_size,
cn_corr_thresh,
...
```

**Lookup always falls through** (`parameters_panel.py`, line 95):

```python
current = data.get(key, "---")  # key="max_iterations", but data has "nn_max_iterations"
```

### Root Cause (Secondary)

Two additional contributing factors compounded the flakiness:

1. **Synchronous HTTP in callback**: The apply-parameters callback used `requests.post()` with a 2-second timeout to send parameters to the cascor backend. Under load or when the backend was slow, this synchronous call blocked the Dash callback thread, causing timeouts and failed updates. This is a Dash anti-pattern -- callbacks should be non-blocking.

2. **Incomplete WebSocket broadcast**: After applying parameters, the WebSocket broadcast only sent `TrainingState` fields (loss, accuracy, epoch, hidden units) -- not the full parameter set. The parameters panel had no way to receive confirmation of the applied values through the real-time update channel, relying entirely on the store propagation that was broken by the prefix mismatch.

### Fix Applied

Added a prefix-stripping callback in `dashboard_manager.py` (lines 1489-1510) that transforms the `applied-params-store` data before propagating it to the parameters panel:

```python
@self.app.callback(
    Output("parameters-panel-params-store", "data"),
    Input("applied-params-store", "data"),
    dash.dependencies.State("visualization-tabs", "active_tab"),
)
def update_parameters_panel_store(applied_data, active_tab):
    """Propagate applied parameters to the parameters panel store.

    Strips nn_/cn_ prefixes so the parameters panel can look up
    values by their unprefixed canonical names.
    """
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

This transforms `{"nn_max_iterations": 500, "cn_pool_size": 100, ...}` into `{"max_iterations": 500, "pool_size": 100, ...}`, matching the keys expected by `parameters_panel.py`.

The secondary issues (synchronous HTTP and incomplete WebSocket broadcast) remain as future improvement items but are lower priority now that the primary data flow is functioning correctly.
