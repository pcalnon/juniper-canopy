# Meta Pa./worktrees/juniper-canopy--feature--meta-parameters-left-menu--20260321-0057--2905f3ab/notes/META_PARAMETERS_ENHANCEMENT_[PLAN.md](http://PLAN.md)rameters Enhancement Plan

**Feature**: Rename Training Parameters to Meta Parameters with Neural Network and Candidate Nodes subsections
**Branch**: `feature/meta-parameters-left-menu`
**Date**: 2026-03-21
**Status**: Planning

---

## 1. Overview

Replace the existing "Training Parameters" card in the left sidebar with a restructured "Meta Parameters" card containing two collapsible subsections:

1. **Neural Network** - Network architecture and training controls
2. **Candidate Nodes** - Cascade correlation candidate pool configuration

Both subsections share a single **Apply Parameters** button. Cross-section checkbox linking connects Multi-Node Layers (NN) with Multi Candidate Selection (CN).

### Current State

The Training Parameters card (`dashboard_manager.py` lines 417-512) contains a flat list of 6 inputs:

- Learning Rate (float, default: 0.01)
- Max Hidden Units (int, default: 20)
- Maximum Epochs (int, default: 300)
- Convergence Detection checkbox (default: enabled)
- Convergence Threshold (float, default: 0.001)
- Spiral Rotations (float, default: 3.0)
- Apply Parameters button + status display

### Target State

Two collapsible subsections with 22 total input components, radio button groups for mutually exclusive options, conditional enable/disable behavior, and cross-section checkbox linking.

---

## 2. Component ID Registry

### 2.1 Neural Network Subsection (12 inputs)

| #  | Component             | ID                                      | Type           | Default         | New/Changed                                   |
|----|-----------------------|-----------------------------------------|----------------|-----------------|-----------------------------------------------|
| 1  | Maximum Iterations    | `nn-max-iterations-input`               | number (int)   | 1000            | NEW                                           |
| 2  | Maximum Total Epochs  | `nn-max-total-epochs-input`             | number (int)   | 1000000         | NEW (replaces `max-epochs-input`)             |
| 3  | Learning Rate         | `nn-learning-rate-input`                | number (float) | 0.01            | RENAMED (was `learning-rate-input`)           |
| 4  | Maximum Hidden Units  | `nn-max-hidden-units-input`             | number (int)   | 1000            | RENAMED + default change (was 20)             |
| 5  | Multi-Node Layers     | `nn-multi-node-layers-checkbox`         | dcc.Checklist  | unchecked       | NEW                                           |
| 6  | Growth Trigger Radio  | `nn-growth-trigger-radio`               | dbc.RadioItems | `"convergence"` | NEW (replaces `convergence-enabled-checkbox`) |
| 7  | Preset Epochs Count   | `nn-growth-preset-epochs-input`         | number (int)   | 50              | NEW                                           |
| 8  | Convergence Threshold | `nn-growth-convergence-threshold-input` | number (float) | 0.001           | RENAMED (was `convergence-threshold-input`)   |
| 9  | Spiral Rotations      | `nn-spiral-rotations-input`             | number (float) | 1.5             | RENAMED + default change (was 3.0)            |
| 10 | Spiral Number         | `nn-spiral-number-input`                | number (int)   | 2               | NEW                                           |
| 11 | Dataset Elements      | `nn-dataset-elements-input`             | number (int)   | 1000            | NEW                                           |
| 12 | Dataset Noise         | `nn-dataset-noise-input`                | number (float) | 0.25            | NEW                                           |

### 2.2 Candidate Nodes Subsection (10 inputs)

| #   | Component                 | ID                                        | Type           | Default             | New/Changed |
| --- | ------------------------- | ----------------------------------------- | -------------- | ------------------- | ----------- |
| 1   | Candidate Pool Size       | `cn-pool-size-input`                      | number (int)   | 100                 | NEW         |
| 2   | Correlation Threshold     | `cn-correlation-threshold-input`          | number (float) | 0.001               | NEW         |
| 3   | Selected Candidates       | `cn-selected-candidates-input`            | number (int)   | 1                   | NEW         |
| 4   | Pool Training Radio       | `cn-training-complete-radio`              | dbc.RadioItems | `"preset_epochs"`   | NEW         |
| 5   | Training Iterations       | `cn-training-iterations-input`            | number (int)   | 500                 | NEW         |
| 6   | CN Convergence Threshold  | `cn-training-convergence-threshold-input` | number (float) | 0.0001              | NEW         |
| 7   | Multi Candidate Selection | `cn-multi-candidate-checkbox`             | dcc.Checklist  | unchecked           | NEW         |
| 8   | Candidate Selection Radio | `cn-candidate-selection-radio`            | dbc.RadioItems | None (no selection) | NEW         |
| 9   | Top Candidates Count      | `cn-top-candidates-input`                 | number (int)   | 1                   | NEW         |
| 10  | Random Candidates Count   | `cn-random-candidates-input`              | number (int)   | 1                   | NEW         |

### 2.3 Structural IDs

| Component           | ID                       | Purpose                   |
| ------------------- | ------------------------ | ------------------------- |
| NN section header   | `nn-subsection-header`   | Collapsible toggle        |
| NN section icon     | `nn-subsection-icon`     | Expand/collapse indicator |
| NN section collapse | `nn-subsection-collapse` | dbc.Collapse wrapper      |
| CN section header   | `cn-subsection-header`   | Collapsible toggle        |
| CN section icon     | `cn-subsection-icon`     | Expand/collapse indicator |
| CN section collapse | `cn-subsection-collapse` | dbc.Collapse wrapper      |
| Apply button        | `apply-params-button`    | Shared (unchanged ID)     |
| Status display      | `params-status`          | Shared (unchanged ID)     |

### 2.4 Removed Component IDs

| Old ID                         | Reason                                             |
|--------------------------------|----------------------------------------------------|
| `learning-rate-input`          | Renamed to `nn-learning-rate-input`                |
| `max-hidden-units-input`       | Renamed to `nn-max-hidden-units-input`             |
| `max-epochs-input`             | Replaced by `nn-max-total-epochs-input`            |
| `convergence-enabled-checkbox` | Replaced by `nn-growth-trigger-radio`              |
| `convergence-threshold-input`  | Renamed to `nn-growth-convergence-threshold-input` |
| `spiral-rotations-input`       | Renamed to `nn-spiral-rotations-input`             |

---

## 3. Constants Changes (`canopy_constants.py`)

### 3.1 Modified Existing Constants

```python
# Epoch limits - CHANGED
DEFAULT_TRAINING_EPOCHS: Final[int] = 1000000    # was 300
MAX_TRAINING_EPOCHS: Final[int] = 10000000       # was 1000

# Hidden units - CHANGED
DEFAULT_MAX_HIDDEN_UNITS: Final[int] = 1000      # was 20
MAX_HIDDEN_UNITS: Final[int] = 10000             # was 20

# Spiral - CHANGED
DEFAULT_SPIRAL_ROTATIONS: Final[float] = 1.5     # was 3.0
```

### 3.2 New Neural Network Constants

```python
# Maximum Iterations (network growth and output training)
DEFAULT_MAX_ITERATIONS: Final[int] = 1000
MIN_MAX_ITERATIONS: Final[int] = 1
MAX_MAX_ITERATIONS: Final[int] = 100000

# Preset Epochs (growth trigger)
DEFAULT_PRESET_EPOCHS: Final[int] = 50
MIN_PRESET_EPOCHS: Final[int] = 1
MAX_PRESET_EPOCHS: Final[int] = 10000

# Growth trigger mode
DEFAULT_GROWTH_TRIGGER: Final[str] = "convergence"

# Multi-Node Layers
DEFAULT_MULTI_NODE_LAYERS: Final[bool] = False

# Spiral Number
DEFAULT_SPIRAL_NUMBER: Final[int] = 2
MIN_SPIRAL_NUMBER: Final[int] = 1
MAX_SPIRAL_NUMBER: Final[int] = 10

# Dataset Elements
DEFAULT_DATASET_ELEMENTS: Final[int] = 1000
MIN_DATASET_ELEMENTS: Final[int] = 50
MAX_DATASET_ELEMENTS: Final[int] = 50000

# Dataset Noise
DEFAULT_DATASET_NOISE: Final[float] = 0.25
MIN_DATASET_NOISE: Final[float] = 0.0
MAX_DATASET_NOISE: Final[float] = 1.0
```

### 3.3 New Candidate Nodes Constants

```python
# Candidate Pool Size
DEFAULT_CANDIDATE_POOL_SIZE: Final[int] = 100
MIN_CANDIDATE_POOL_SIZE: Final[int] = 1
MAX_CANDIDATE_POOL_SIZE: Final[int] = 500

# Candidate Correlation Threshold
DEFAULT_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.001
MIN_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.00001
MAX_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.1

# Selected Candidates
DEFAULT_SELECTED_CANDIDATES: Final[int] = 1
MIN_SELECTED_CANDIDATES: Final[int] = 1
MAX_SELECTED_CANDIDATES: Final[int] = 50

# Pool Training Complete - Preset Epochs mode
DEFAULT_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 500
MIN_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 10
MAX_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 5000

# Pool Training Complete - Convergence mode
DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.0001
MIN_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.000001
MAX_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.01

# Pool Training Complete mode
DEFAULT_CN_TRAINING_COMPLETE: Final[str] = "preset_epochs"

# Multi Candidate Selection
DEFAULT_MULTI_CANDIDATE_ENABLED: Final[bool] = False
DEFAULT_CN_CANDIDATE_SELECTION: Final[str] = None  # no default selection when checkbox is unchecked

DEFAULT_TOP_CANDIDATES_COUNT: Final[int] = 1
MIN_TOP_CANDIDATES_COUNT: Final[int] = 1
MAX_TOP_CANDIDATES_COUNT: Final[int] = 20

DEFAULT_RANDOM_CANDIDATES_COUNT: Final[int] = 1
MIN_RANDOM_CANDIDATES_COUNT: Final[int] = 1
MAX_RANDOM_CANDIDATES_COUNT: Final[int] = 20
```

---

## 4. Callback Architecture

### 4.1 Callback Summary

| #  | Callback                             | Inputs                       | Outputs                       | States | prevent_initial_call | allow_duplicate             |
|----|--------------------------------------|------------------------------|-------------------------------|--------|----------------------|-----------------------------|
| 1  | `track_param_changes`                | 22 components + 1 store = 23 | 2                             | 0      | No                   | None                        |
| 2  | `apply_parameters`                   | 1 (button click)             | 2                             | 22     | Yes                  | `params-status.children`    |
| 3  | `init_params_from_backend`           | 1 (interval)                 | 23 (22 components + store)    | 1      | Yes                  | `applied-params-store.data` |
| 4  | `sync_multi_node_checkboxes`         | 2 (both checkboxes)          | 2 (both checkboxes)           | 0      | Yes                  | Both outputs                |
| 5  | `toggle_nn_subsection`               | 1 (header click)             | 2 (collapse + icon)           | 1      | Yes                  | None                        |
| 6  | `toggle_cn_subsection`               | 1 (header click)             | 2 (collapse + icon)           | 1      | Yes                  | None                        |
| 7  | `toggle_nn_growth_inputs`            | 1 (radio)                    | 2 (disabled states)           | 0      | No                   | None                        |
| 8  | `toggle_cn_training_inputs`          | 1 (radio)                    | 2 (disabled states)           | 0      | No                   | None                        |
| 9  | `toggle_cn_selection_inputs`         | 1 (radio)                    | 2 (disabled states)           | 0      | No                   | None                        |
| 10 | `toggle_cn_multi_candidate_subgroup` | 1 (checkbox)                 | 3 (radio + 2 inputs disabled) | 0      | No                   | None                        |

**Removed callback**: `handle_parameter_changes` - returns `dash.no_update` unconditionally, only logs. Logging can move to `track_param_changes`.

### 4.5 Multi Candidate Sub-Group Enable/Disable

When `cn-multi-candidate-checkbox` is unchecked (default), the entire sub-group must be disabled:

- `cn-candidate-selection-radio` disabled
- `cn-top-candidates-input` disabled
- `cn-random-candidates-input` disabled

When checked, the radio group enables, and callback #9 applies the radio-based enable/disable to the two count inputs.

```python
def _toggle_cn_multi_candidate_subgroup_handler(self, value):
    enabled = "enabled" in (value or [])
    if not enabled:
        return True, True, True   # all disabled
    return False, False, False    # radio + both inputs enabled (radio-based logic refines this)
```

Note: Callback #9 (`toggle_cn_selection_inputs`) should also check the checkbox state and keep inputs disabled when the checkbox is unchecked, regardless of radio selection.

### 4.2 Cross-Section Checkbox Linking

The `sync_multi_node_checkboxes` callback handles the bidirectional link:

- **NN Multi-Node Layers** (`nn-multi-node-layers-checkbox`) and **CN Multi Candidate Selection** (`cn-multi-candidate-checkbox`)
- Checking CN Multi Candidate also checks NN Multi-Node Layers
- Uses `ctx.triggered_id` to determine which checkbox changed
- Always returns `dash.no_update` for the triggering input to prevent infinite loops

```python
def _sync_multi_node_checkboxes_handler(self, nn_value, cn_value):
    ctx = get_callback_context()
    trigger = ctx.get_triggered_id()
    if trigger == "cn-multi-candidate-checkbox":
        cn_enabled = "enabled" in (cn_value or [])
        if cn_enabled:
            return ["enabled"], dash.no_update  # force NN on
        return dash.no_update, dash.no_update   # don't uncheck NN
    elif trigger == "nn-multi-node-layers-checkbox":
        return dash.no_update, dash.no_update   # NN is independent
    return dash.no_update, dash.no_update
```

### 4.3 Radio Button Enable/Disable Pattern

Each radio group controls `disabled` state of associated inputs:

- **NN Growth Trigger**: `"preset_epochs"` enables preset-epochs-input, disables convergence-threshold-input; `"convergence"` reverses
- **CN Training Complete**: `"preset_epochs"` enables training-iterations-input, disables convergence-threshold-input; `"convergence"` reverses
- **CN Candidate Selection**: `"top_tier"` enables top-candidates-input, disables random-candidates-input; `"random"` reverses

**Label Note**: CN Pool Training Complete uses "Training Iterations" (not "Epochs") for the preset mode sub-field to distinguish from NN growth trigger terminology. The radio label is "Preset Epochs" per requirements, but the associated input label is "Training Iterations".

### 4.4 Applied Params Store Structure

```python
{
    # Neural Network
    "nn_max_iterations": 1000,
    "nn_max_total_epochs": 1000000,
    "nn_learning_rate": 0.01,
    "nn_max_hidden_units": 1000,
    "nn_multi_node_layers": False,
    "nn_growth_trigger": "convergence",
    "nn_growth_preset_epochs": 50,
    "nn_growth_convergence_threshold": 0.001,
    "nn_spiral_rotations": 1.5,
    "nn_spiral_number": 2,
    "nn_dataset_elements": 1000,
    "nn_dataset_noise": 0.25,
    # Candidate Nodes
    "cn_pool_size": 100,
    "cn_correlation_threshold": 0.001,
    "cn_selected_candidates": 1,
    "cn_training_complete": "preset_epochs",
    "cn_training_iterations": 500,
    "cn_training_convergence_threshold": 0.0001,
    "cn_multi_candidate": False,
    "cn_candidate_selection": None,  # no default; sub-group disabled when checkbox unchecked
    "cn_top_candidates": 1,
    "cn_random_candidates": 1,
}
```

---

## 5. Backend API Changes

### 5.1 `/api/set_params` Endpoint (`main.py`)

Expand to accept all 22 parameter keys with `nn_` and `cn_` prefixes. Map `nn_learning_rate`, `nn_max_hidden_units`, `nn_max_total_epochs` to `TrainingState.update_state()` for backward compatibility. Forward all params to `backend.apply_params()`.

### 5.2 `/api/state` Endpoint

Include all 22 meta-parameter fields in the state response. Use `.get()` with `TrainingConstants` defaults for any missing fields to handle backward compatibility when the backend doesn't yet store all parameters.

### 5.3 `DemoMode.apply_params()` (`demo_mode.py`)

Extend to accept and store all new `nn_*` and `cn_*` keyword arguments. Unknown keys should be stored and accessible but not cause errors.

### 5.4 `settings.py`

Update `TrainingSettings` model to include new `TrainingParamConfig` entries:

```python
class TrainingSettings(BaseModel):
    epochs: TrainingParamConfig = TrainingParamConfig(min=10, max=10000000, default=1000000)
    learning_rate: TrainingParamConfig = TrainingParamConfig(min=0.0001, max=1.0, default=0.01)
    hidden_units: TrainingParamConfig = TrainingParamConfig(min=0, max=10000, default=1000)
    max_iterations: TrainingParamConfig = TrainingParamConfig(min=1, max=100000, default=1000)
    preset_epochs: TrainingParamConfig = TrainingParamConfig(min=1, max=10000, default=50)
```

---

## 6. Layout Design

### 6.1 Card Structure

```bash
dbc.Card (className="mb-3")
  dbc.CardHeader -> html.H5("Meta Parameters")
  dbc.CardBody
    html.H6 [nn-subsection-header] (collapsible-header)
      Span [nn-subsection-icon] "▼"
      "Neural Network"
    dbc.Collapse [nn-subsection-collapse] (is_open=True)
      nn-max-iterations-input
      nn-max-total-epochs-input
      nn-learning-rate-input
      nn-max-hidden-units-input
      nn-multi-node-layers-checkbox
      html.Hr
      "Network Growth Triggers:" label
      nn-growth-trigger-radio (default: "convergence")
        nn-growth-preset-epochs-input (disabled=True; convergence is default)
        nn-growth-convergence-threshold-input (disabled=False)
      html.Hr
      "Spiral Dataset" sub-header
        "Spiral:" label
          nn-spiral-rotations-input
          nn-spiral-number-input
        "Dataset:" label
          nn-dataset-elements-input
          nn-dataset-noise-input

    html.Hr
    html.H6 [cn-subsection-header] (collapsible-header)
      Span [cn-subsection-icon] "▶"
      "Candidate Nodes"
    dbc.Collapse [cn-subsection-collapse] (is_open=False)
      cn-pool-size-input
      cn-correlation-threshold-input
      cn-selected-candidates-input
      html.Hr
      "Pool Training Complete:" label
      cn-training-complete-radio (default: "preset_epochs")
        cn-training-iterations-input (disabled=False; preset_epochs is default)
        cn-training-convergence-threshold-input (disabled=True)
      html.Hr
      "Multi Candidate Selection:" label
      cn-multi-candidate-checkbox (unchecked)
        cn-candidate-selection-radio (disabled=True; checkbox unchecked by default)
          cn-top-candidates-input (disabled=True)
          cn-random-candidates-input (disabled=True)

    html.Hr
    Apply Parameters button [apply-params-button]
    Status display [params-status]
```

### 6.2 Radio Button Sub-field Pattern

For each radio group, associated inputs are indented (`ms-3` or `ms-4`) and conditionally disabled:

```python
html.P("Network Growth Triggers:", className="mb-1 fw-bold"),
dbc.RadioItems(
    id="nn-growth-trigger-radio",
    options=[
        {"label": "Preset Epochs", "value": "preset_epochs"},
        {"label": "Convergence Detection", "value": "convergence"},
    ],
    value="convergence",
    className="mb-2",
),
html.Div([
    html.P("Number of Epochs:", className="mb-1 ms-4"),
    dbc.Input(id="nn-growth-preset-epochs-input", ..., disabled=True),
], id="nn-growth-preset-epochs-container"),
html.Div([
    html.P("Convergence Threshold:", className="mb-1 ms-4"),
    dbc.Input(id="nn-growth-convergence-threshold-input", ..., disabled=False),
], id="nn-growth-convergence-threshold-container"),
```

---

## 7. Risks and Guardrails

### 7.1 Breaking Changes

| Risk                                                   | Impact                                          | Mitigation                                                                            |
|--------------------------------------------------------|-------------------------------------------------|---------------------------------------------------------------------------------------|
| Removed `convergence-enabled-checkbox` ID              | Tests referencing this ID break                 | Update all tests; map `convergence_enabled` from `nn_growth_trigger == "convergence"` |
| Renamed component IDs                                  | Callbacks referencing old IDs break             | Comprehensive search-and-replace; update all test files                               |
| Changed default values                                 | Existing users see different defaults           | Document in release notes                                                             |
| `init_params_from_backend` tuple size change (7 -> 23) | Off-by-one errors cause Dash runtime exceptions | Unit test the exact tuple length                                                      |

### 7.2 Circular Dependency Risk

The `sync_multi_node_checkboxes` callback has components as both Input and Output. This is safe because:

- `allow_duplicate=True` is set on both outputs
- Handler returns `dash.no_update` for the triggering component
- Dash de-duplicates no-change updates, preventing infinite loops

### 7.3 Performance

22 inputs on `track_param_changes` is significant but safe because:

- All numeric inputs use `debounce=True` (fires on blur/Enter, not per-keystroke)
- Radio items and checkboxes fire immediately but handler logic is O(1) comparisons
- No API calls in the tracking callback

### 7.4 Backward Compatibility

| Area                          | Risk                             | Mitigation                                                                   |
|-------------------------------|----------------------------------|------------------------------------------------------------------------------|
| `/api/set_params` payload     | Old clients send old keys        | Accept both old and new keys; map old -> new internally                      |
| `/api/state` response         | Old fields missing               | Always provide defaults via `.get()` with `TrainingConstants` fallbacks      |
| `applied-params-store` format | Incompatible with old store data | Store starts empty; `init_params_from_backend` repopulates on each page load |
| `DemoMode.apply_params()`     | Unknown kwargs                   | Accept `**kwargs` to absorb unrecognized params gracefully                   |

### 7.5 UI Overflow

The Meta Parameters card will be 2-3x taller than the current Training Parameters card. Guardrails:

- CN subsection defaults to `is_open=False` (collapsed)
- Both subsections are independently collapsible
- Left sidebar has natural scroll from the browser

---

## 8. Test Plan

### 8.1 Unit Tests - Layout Verification

| Test                                                 | Validates              |
|------------------------------------------------------|------------------------|
| All 22 input component IDs exist in layout           | Component registration |
| All structural IDs exist (headers, collapses, icons) | Section structure      |
| Default values match `TrainingConstants`             | Constant integration   |
| Radio button options have correct values             | Option configuration   |
| Checkboxes default to unchecked                      | Initial state          |
| Apply button starts disabled                         | Initial state          |

### 8.2 Unit Tests - Callback Handlers

| Test                                                                          | Validates          |
|-------------------------------------------------------------------------------|--------------------|
| `_track_param_changes_handler` with no changes returns disabled               | Dirty tracking     |
| `_track_param_changes_handler` with float change detected                     | Float tolerance    |
| `_track_param_changes_handler` with radio change detected                     | String comparison  |
| `_track_param_changes_handler` with checkbox change detected                  | Bool comparison    |
| `_apply_parameters_handler` builds correct params dict                        | Param construction |
| `_apply_parameters_handler` handles None values with defaults                 | Null safety        |
| `_init_params_from_backend_handler` returns 23-tuple                          | Tuple length       |
| `_init_params_from_backend_handler` with current_applied returns no_update    | Short-circuit      |
| `_sync_multi_node_checkboxes_handler` CN triggers NN                          | Cross-section link |
| `_sync_multi_node_checkboxes_handler` NN does not trigger CN                  | Independence       |
| `_toggle_nn_growth_inputs_handler` preset_epochs mode                         | Radio disable      |
| `_toggle_nn_growth_inputs_handler` convergence mode                           | Radio disable      |
| `_toggle_cn_training_inputs_handler` both modes                               | Radio disable      |
| `_toggle_cn_selection_inputs_handler` both modes                              | Radio disable      |
| `_toggle_cn_multi_candidate_subgroup_handler` checkbox unchecked disables all | Sub-group disable  |
| `_toggle_cn_multi_candidate_subgroup_handler` checkbox checked enables all    | Sub-group enable   |

### 8.3 Integration Tests

| Test                                              | Validates           |
|---------------------------------------------------|---------------------|
| POST `/api/set_params` with full new payload      | API acceptance      |
| POST `/api/set_params` with partial payload       | Backward compat     |
| POST `/api/set_params` with old-style keys        | Legacy support      |
| GET `/api/state` includes all 22 fields           | State completeness  |
| `DemoMode.apply_params()` accepts all new params  | Backend integration |
| Round-trip: apply -> state -> verify values match | End-to-end          |

### 8.4 Existing Tests Requiring Updates

| File                                 | Changes Needed                                                            |
|--------------------------------------|---------------------------------------------------------------------------|
| `test_convergence_layout.py`         | Update for removed `convergence-enabled-checkbox`, new radio group        |
| `test_convergence_ui_controls.py`    | Update handler call signatures                                            |
| `test_apply_button_parameters.py`    | Update API payload keys and handler args                                  |
| `test_dashboard_manager.py`          | Update callback registration counts                                       |
| `test_config_training_params.py`     | Update for changed default values                                         |
| `test_convergence_ui_regression.py`  | Update handler call signatures                                            |
| `test_dashboard_manager_handlers.py` | Update handler call signatures                                            |
| `test_dashboard_manager_95.py`       | Update for renamed component IDs                                          |
| `test_max_epochs_parameter.py`       | 11+ references to `max-epochs-input` and old IDs; update all              |
| `test_dashboard_enhancements.py`     | References `max-epochs-input`, old IDs, and `"Training Parameters"` label |

---

## 9. Implementation Phases

### Phase 1: Foundation (Constants + Settings)

1. Update `canopy_constants.py` with all new and changed constants
2. Update `settings.py` `TrainingSettings` model
3. Run existing tests to identify baseline failures from constant changes

### Phase 2: Backend API

1. Update `/api/set_params` endpoint to accept new keys
2. Update `/api/state` endpoint to return all meta-parameter fields
3. Update `DemoMode.apply_params()` to accept new parameters
4. Update `DemoBackend.apply_params()` to forward new params to DemoMode
5. Update `TrainingState` if needed for new fields
6. Update `settings.py` `get_training_defaults()` to return new parameter defaults

### Phase 3: Layout

1. Replace Training Parameters card with Meta Parameters card
2. Add Neural Network subsection layout with all 12 inputs
3. Add Candidate Nodes subsection layout with all 10 inputs
4. Keep shared Apply button and status display

### Phase 4: Callbacks

1. Add collapsible toggle callbacks (NN + CN sections)
2. Add radio-to-disable callbacks (3 total)
3. Add multi-candidate sub-group enable/disable callback
4. Add cross-section checkbox sync callback
5. Rewrite `track_param_changes` with 23 inputs
6. Rewrite `apply_parameters` with 22 State values
7. Rewrite `init_params_from_backend` with 23 outputs
8. Remove obsolete `handle_parameter_changes` callback

### Phase 5: Tests

1. Update all broken existing tests
2. Add new unit tests for layout verification
3. Add new unit tests for all handler methods
4. Add new integration tests for API endpoints
5. Run full test suite and fix failures

### Phase 6: Finalize

1. Run linters (black, isort, flake8)
2. Commit and push
3. Create pull request

---

## 10. Files Modified

| File                                                            | Type of Change                                                      |
|-----------------------------------------------------------------|---------------------------------------------------------------------|
| `src/canopy_constants.py`                                       | New + modified constants                                            |
| `src/settings.py`                                               | Updated TrainingSettings model                                      |
| `src/frontend/dashboard_manager.py`                             | Layout, callbacks, handlers (major rewrite)                         |
| `src/main.py`                                                   | `/api/set_params` and `/api/state` endpoints                        |
| `src/demo_mode.py`                                              | `apply_params()` expansion                                          |
| `src/backend/demo_backend.py`                                   | `apply_params()` must forward new `nn_*`/`cn_*` params to DemoMode  |
| `src/settings.py` (also)                                        | `get_training_defaults()` method must return new parameter defaults |
| `src/tests/unit/frontend/test_convergence_layout.py`            | Update for new structure                                            |
| `src/tests/unit/test_convergence_ui_controls.py`                | Update handler signatures                                           |
| `src/tests/integration/test_apply_button_parameters.py`         | Update API payload + handler args                                   |
| `src/tests/unit/frontend/test_dashboard_manager.py`             | Update callback counts                                              |
| `src/tests/unit/test_config_training_params.py`                 | Update default values                                               |
| `src/tests/unit/test_max_epochs_parameter.py`                   | Update all old component ID references                              |
| `src/tests/integration/test_dashboard_enhancements.py`          | Update old IDs and "Training Parameters" label                      |
| New: `src/tests/unit/frontend/test_meta_parameters_layout.py`   | Layout verification tests                                           |
| New: `src/tests/unit/frontend/test_meta_parameters_handlers.py` | Handler unit tests                                                  |
| New: `src/tests/integration/test_meta_parameters_api.py`        | API integration tests                                               |

---

## 11. Risk Prioritization

| Priority | Risk                                      | Likelihood | Impact      | Mitigation                                      |
|----------|-------------------------------------------|------------|-------------|-------------------------------------------------|
| P0       | `init_params_from_backend` tuple mismatch | High       | App crash   | Unit test exact tuple length                    |
| P0       | Removed component IDs break callbacks     | High       | App crash   | Search all references before removing           |
| P1       | Circular dependency in checkbox sync      | Medium     | App crash   | Test with `dash.testing` or manual verification |
| P1       | Float comparison false positives          | Low        | UX bug      | Use existing `float_equal` pattern consistently |
| P2       | UI overflow on small screens              | Low        | UX issue    | CN section collapsed by default                 |
| P2       | Backend rejects unknown params            | Low        | Apply fails | Use `**kwargs` pattern in `apply_params()`      |

---
