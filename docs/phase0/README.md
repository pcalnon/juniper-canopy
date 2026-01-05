# Phase 0: Core UX Stabilization

**Last Updated:** 2025-12-12  
**Version:** 1.0.0  
**Status:** Ready for Implementation

## Overview

Phase 0 addresses critical bugs that make the dashboard feel unreliable. These P0 fixes are the foundation for all subsequent enhancements.

**Estimated Effort:** 1-2 days  
**Target Coverage After Phase 0:** 88%

---

## Table of Contents

- [P0-1: Training Controls Button State Fix](#p0-1-training-controls-button-state-fix)
- [P0-2: Meta-Parameters Apply Button](#p0-2-meta-parameters-apply-button)
- [P0-3: Top Status Bar Updates](#p0-3-top-status-bar-updates)
- [P0-4: Graph Range Persistence](#p0-4-graph-range-persistence)
- [P0-5: Pan/Lasso Tool Fix](#p0-5-panlasso-tool-fix)
- [P0-6: Interaction Persistence](#p0-6-interaction-persistence)
- [P0-7: Dark Mode Info Bar](#p0-7-dark-mode-info-bar)
- [Implementation Order](#implementation-order)

---

## P0-1: Training Controls Button State Fix

### Problem

After a button is pressed, it stays in "pressed" state and never returns to "unpressed" state. This affects all 5 buttons (Start, Pause, Resume, Stop, Reset).

### Root Cause Analysis

In `dashboard_manager.py`:

- `_handle_training_buttons_handler` sets button to loading state
- `_handle_button_timeout_and_acks_handler` should re-enable but logic is incomplete
- Race conditions between debouncing and timeout handling

### Solution Design

```python
# Changes to dashboard_manager.py

# 1. Simplify button states store initialization
dcc.Store(
    id="training-button-states",
    data={
        "start": {"disabled": False, "loading": False, "timestamp": 0},
        "pause": {"disabled": False, "loading": False, "timestamp": 0},
        "stop": {"disabled": False, "loading": False, "timestamp": 0},
        "resume": {"disabled": False, "loading": False, "timestamp": 0},
        "reset": {"disabled": False, "loading": False, "timestamp": 0},
    }
)

# 2. Fix timeout handler to always check all buttons
def _handle_button_timeout_and_acks_handler(self, n_intervals=None, button_states=None):
    """Re-enable buttons after timeout (2s) or on command success."""
    if not button_states:
        return button_states

    current_time = time.time()
    new_states = {}
    changed = False

    for cmd, state in button_states.items():
        if state.get("loading") and state.get("timestamp", 0) > 0:
            elapsed = current_time - state["timestamp"]
            if elapsed > 2.0:  # 2 second timeout
                new_states[cmd] = {"disabled": False, "loading": False, "timestamp": 0}
                changed = True
            else:
                new_states[cmd] = state
        else:
            new_states[cmd] = state

    return new_states if changed else dash.no_update
```

### Files to Modify

- `src/frontend/dashboard_manager.py`
  - `_setup_layout()` - Update button-states store structure
  - `_setup_callbacks()` - Simplify button callback chain
  - `_handle_training_buttons_handler()` - Add timestamp to state
  - `_handle_button_timeout_and_acks_handler()` - Fix timeout logic
  - `_update_button_appearance_handler()` - Ensure state reset

### Tests to Add

```python
# tests/unit/test_button_state_fixes.py

def test_button_returns_to_normal_after_click():
    """Button should return to normal state after successful command."""

def test_button_returns_to_normal_after_timeout():
    """Button should return to normal after 2 second timeout."""

def test_button_clickable_after_reset():
    """Button should be clickable after state reset."""

def test_all_buttons_independent():
    """Each button's state should be independent of others."""

def test_rapid_clicks_debounced():
    """Rapid clicks within 500ms should be debounced."""
```

---

## P0-2: Meta-Parameters Apply Button

### Problem. P0-2

Meta-parameters are not applied after being changed. Need manual Apply button.

### Solution Design, P0-2

```python
# Add to _setup_layout() after meta-parameter inputs

html.Hr(),
html.Div(
    [
        dbc.Button(
            "Apply Parameters",
            id="apply-params-button",
            className="w-100 mb-2",
            color="primary",
            disabled=True,  # Disabled until changes made
        ),
        html.Div(
            id="params-status",
            children="",
            style={"fontSize": "0.85em", "color": "#6c757d"}
        ),
    ]
),

# Add stores for pending vs applied parameters
dcc.Store(
    id="pending-params-store",
    data={"learning_rate": None, "hidden_units": None, "epochs": None}
),
dcc.Store(
    id="applied-params-store",
    data={}  # Populated from backend on load
),
```

### Callback Logic

```python
@self.app.callback(
    Output("apply-params-button", "disabled"),
    Output("params-status", "children"),
    Input("learning-rate-input", "value"),
    Input("max-hidden-units-input", "value"),
    Input("max-epochs-input", "value"),
    State("applied-params-store", "data"),
)
def track_param_changes(lr, hu, epochs, applied):
    """Track parameter changes and enable Apply button."""
    has_changes = (
        lr != applied.get("learning_rate") or
        hu != applied.get("hidden_units") or
        epochs != applied.get("epochs")
    )

    status = "Unsaved changes" if has_changes else ""
    return not has_changes, status

@self.app.callback(
    Output("applied-params-store", "data"),
    Output("params-status", "children", allow_duplicate=True),
    Input("apply-params-button", "n_clicks"),
    State("learning-rate-input", "value"),
    State("max-hidden-units-input", "value"),
    State("max-epochs-input", "value"),
    prevent_initial_call=True,
)
def apply_parameters(n_clicks, lr, hu, epochs):
    """Apply parameters to backend and update applied store."""
    if not n_clicks:
        return dash.no_update, dash.no_update

    params = {
        "learning_rate": float(lr),
        "max_hidden_units": int(hu),
        "max_epochs": int(epochs),
    }

    try:
        response = requests.post(
            self._api_url("/api/set_params"),
            json=params,
            timeout=2
        )
        if response.status_code == 200:
            return params, "Parameters applied ✓"
        return dash.no_update, "Failed to apply parameters"
    except Exception as e:
        return dash.no_update, f"Error: {str(e)}"
```

### Files to Modify, P0-2

- `src/frontend/dashboard_manager.py`
  - `_setup_layout()` - Add Apply button and stores
  - `_setup_callbacks()` - Add parameter tracking callbacks
  - Remove automatic parameter sending from input change handlers

### Tests to Add, P0-2

```python
# tests/unit/test_parameter_apply.py

def test_apply_button_disabled_initially():
    """Apply button should be disabled with no changes."""

def test_apply_button_enabled_on_change():
    """Apply button should enable when parameters change."""

def test_apply_sends_to_backend():
    """Apply button should send parameters to backend."""

def test_apply_updates_applied_store():
    """Apply should update applied-params-store on success."""

def test_unsaved_indicator_shown():
    """'Unsaved changes' should appear when params differ."""
```

---

## P0-3: Top Status Bar Updates

### Problem, P0-3

Status always shows "Stopped" and Phase always shows "Idle" regardless of actual training state.

### Root Cause Analysis, P0-3

`_update_top_status_phase_handler` fetches from `/api/state` but the response mapping may not match actual training states.

### Solution Design, P0-3

```python
def _get_status_phase_display_content(self, state_response=None):
    """Map backend state to display values."""
    state_data = state_response.json()

    # Get raw values
    is_running = state_data.get("is_running", False)
    is_paused = state_data.get("is_paused", False)
    current_phase = state_data.get("phase", "idle").lower()

    # Determine display status
    if is_running and not is_paused:
        status = "Running"
        status_color = "#28a745"  # Green
    elif is_paused:
        status = "Paused"
        status_color = "#ffc107"  # Orange
    elif state_data.get("completed", False):
        status = "Completed"
        status_color = "#17a2b8"  # Cyan
    elif state_data.get("failed", False):
        status = "Failed"
        status_color = "#dc3545"  # Red
    else:
        status = "Stopped"
        status_color = "#6c757d"  # Gray

    # Determine display phase
    phase_map = {
        "idle": ("Idle", "#6c757d"),
        "output": ("Output Training", "#007bff"),
        "candidate": ("Candidate Pool", "#17a2b8"),
        "installing": ("Installing Unit", "#6610f2"),
    }

    phase, phase_color = phase_map.get(
        current_phase,
        (current_phase.title(), "#6c757d")
    )

    return (
        status,
        {"fontWeight": "bold", "color": status_color},
        phase,
        {"fontWeight": "bold", "color": phase_color},
    )
```

### Files to Modify, P0-3

- `src/frontend/dashboard_manager.py`
  - `_get_status_phase_display_content()` - Fix state mapping
  - Ensure interval callback triggers properly

- `src/main.py` (if needed)
  - Verify `/api/state` returns correct fields

### Tests to Add, P0-3

```python
# tests/unit/test_status_bar_display.py

def test_status_shows_running_when_running():
    """Status should show 'Running' when is_running=True."""

def test_status_shows_paused_when_paused():
    """Status should show 'Paused' when is_paused=True."""

def test_phase_shows_output_training():
    """Phase should show 'Output Training' for output phase."""

def test_phase_shows_candidate_pool():
    """Phase should show 'Candidate Pool' for candidate phase."""

def test_colors_match_state():
    """Colors should match state (green=running, orange=paused, etc)."""
```

---

## P0-4: Graph Range Persistence

### Problem, P0-4

When a range is selected on Training graphs, the display resets in ~1 second.

### Root Cause Analysis, P0-4

Interval-driven callbacks recreate the entire figure, overwriting user's zoom/pan state.

### Solution Design, P0-4

**Strategy: Preserve layout on data updates using figure patching.**

```python
# In metrics_panel.py

# Add view state store
dcc.Store(id=f"{self.component_id}-view-state", data={
    "loss_xaxis_range": None,
    "loss_yaxis_range": None,
    "accuracy_xaxis_range": None,
    "accuracy_yaxis_range": None,
})

# Callback to capture user's zoom/pan
@self.app.callback(
    Output(f"{self.component_id}-view-state", "data"),
    Input(f"{self.component_id}-loss-graph", "relayoutData"),
    Input(f"{self.component_id}-accuracy-graph", "relayoutData"),
    State(f"{self.component_id}-view-state", "data"),
    prevent_initial_call=True,
)
def capture_view_state(loss_relayout, acc_relayout, current_state):
    """Capture user's zoom/pan state."""
    ctx = dash.callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    new_state = current_state.copy()

    if "loss-graph" in trigger and loss_relayout:
        if "xaxis.range[0]" in loss_relayout:
            new_state["loss_xaxis_range"] = [
                loss_relayout["xaxis.range[0]"],
                loss_relayout["xaxis.range[1]"],
            ]
        if "yaxis.range[0]" in loss_relayout:
            new_state["loss_yaxis_range"] = [
                loss_relayout["yaxis.range[0]"],
                loss_relayout["yaxis.range[1]"],
            ]
        # Handle autosize/reset
        if "xaxis.autorange" in loss_relayout:
            new_state["loss_xaxis_range"] = None
        if "yaxis.autorange" in loss_relayout:
            new_state["loss_yaxis_range"] = None

    # Similar for accuracy graph...

    return new_state

# Modify graph update to apply stored ranges
def update_loss_graph(self, metrics_data, view_state, theme):
    """Update loss graph preserving user's zoom state."""
    fig = self._create_loss_figure(metrics_data, theme)

    # Apply stored view state if exists
    if view_state.get("loss_xaxis_range"):
        fig.update_layout(xaxis_range=view_state["loss_xaxis_range"])
    if view_state.get("loss_yaxis_range"):
        fig.update_layout(yaxis_range=view_state["loss_yaxis_range"])

    return fig
```

### Files to Modify, P0-4

- `src/frontend/components/metrics_panel.py`
  - `get_layout()` - Add view-state store
  - `register_callbacks()` - Add relayoutData capture callback
  - `update_loss_graph()` - Apply stored ranges
  - `update_accuracy_graph()` - Apply stored ranges
  - Add reset button to clear view state

### Tests to Add, P0-4

```python
# tests/integration/test_range_persistence.py

def test_zoom_persists_across_updates():
    """User's zoom should persist when data updates."""

def test_pan_persists_across_updates():
    """User's pan position should persist when data updates."""

def test_reset_clears_zoom():
    """Reset button should clear zoom state."""

def test_relayout_captured_correctly():
    """relayoutData should be captured to store."""
```

---

## P0-5: Pan/Lasso Tool Fix

### Problem, P0-5

Pan, Lasso Select, and Box Select tools all perform Box Select.

### Solution Design, P0-5

```python
# In network_visualizer.py

def _create_figure(self, topology_data, theme):
    """Create network topology figure with correct tool config."""
    fig = go.Figure()

    # ... add traces ...

    fig.update_layout(
        dragmode="pan",  # Default to pan mode
        selectdirection="any",  # Don't restrict selection
        modebar=dict(
            add=[
                "pan2d",
                "select2d",
                "lasso2d",
                "zoom2d",
                "zoomin2d",
                "zoomout2d",
                "autoScale2d",
                "resetScale2d",
            ],
            remove=["toImage"],  # We'll add custom download
        ),
    )

    return fig

# Store tool selection
dcc.Store(id=f"{self.component_id}-tool-state", data={"dragmode": "pan"})

# Capture tool changes
@self.app.callback(
    Output(f"{self.component_id}-tool-state", "data"),
    Input(f"{self.component_id}-graph", "relayoutData"),
    State(f"{self.component_id}-tool-state", "data"),
    prevent_initial_call=True,
)
def capture_tool_selection(relayout, current):
    """Capture user's tool selection."""
    if relayout and "dragmode" in relayout:
        return {"dragmode": relayout["dragmode"]}
    return current

# Apply tool state on figure update
def update_network_graph(self, topology_data, tool_state, theme):
    """Update network graph preserving tool selection."""
    fig = self._create_figure(topology_data, theme)

    if tool_state and tool_state.get("dragmode"):
        fig.update_layout(dragmode=tool_state["dragmode"])

    return fig
```

### Files to Modify, P0-5

- `src/frontend/components/network_visualizer.py`
  - `get_layout()` - Add tool-state store
  - `_create_figure()` - Set correct dragmode defaults
  - `register_callbacks()` - Add tool capture callback
  - `update_network_graph()` - Apply stored tool state

### Tests to Add, P0-5

```python
# tests/unit/test_topology_tools.py

def test_pan_tool_performs_pan():
    """Pan tool should pan, not box select."""

def test_lasso_tool_performs_lasso():
    """Lasso tool should lasso select."""

def test_tool_selection_persists():
    """Selected tool should persist across updates."""
```

---

## P0-6: Interaction Persistence

### Problem, P0-6

All node interactions (zoom, pan, selection) reset after ~1 second.

### Solution Design, P0-6

**Same pattern as P0-4 and P0-5: Store view state, apply on updates.**

```python
# In network_visualizer.py

dcc.Store(id=f"{self.component_id}-view-state", data={
    "xaxis_range": None,
    "yaxis_range": None,
    "dragmode": "pan",
    "selected_nodes": [],
})

# Only recreate figure if topology actually changed
def update_network_graph(self, topology_data, current_figure, view_state, theme):
    """Update network graph, preserving view state if topology unchanged."""

    # Check if topology changed using hash
    new_hash = self._compute_topology_hash(topology_data)
    if hasattr(self, '_last_topology_hash') and self._last_topology_hash == new_hash:
        # Topology unchanged - just return current figure
        return dash.no_update

    self._last_topology_hash = new_hash

    # Topology changed - create new figure but apply view state
    fig = self._create_figure(topology_data, theme)

    if view_state:
        if view_state.get("xaxis_range"):
            fig.update_layout(xaxis_range=view_state["xaxis_range"])
        if view_state.get("yaxis_range"):
            fig.update_layout(yaxis_range=view_state["yaxis_range"])
        if view_state.get("dragmode"):
            fig.update_layout(dragmode=view_state["dragmode"])

    return fig

def _compute_topology_hash(self, topology_data):
    """Compute hash of topology to detect changes."""
    import hashlib
    import json

    # Hash node count, connection count, and hidden unit count
    key_data = {
        "nodes": len(topology_data.get("nodes", [])),
        "connections": len(topology_data.get("connections", [])),
        "hidden": topology_data.get("hidden_units", 0),
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
```

### Files to Modify, P0-6

- `src/frontend/components/network_visualizer.py`
  - `get_layout()` - Add view-state store
  - `register_callbacks()` - Add view state capture
  - `update_network_graph()` - Check topology hash, apply view state
  - Add `_compute_topology_hash()` method

### Tests to Add, P0-6

```python
# tests/integration/test_topology_persistence.py

def test_zoom_persists_when_topology_unchanged():
    """Zoom should persist when data updates without topology change."""

def test_zoom_reset_on_topology_change():
    """View may reset when topology actually changes."""

def test_pan_persists_across_updates():
    """Pan position should persist across interval updates."""

def test_selection_persists():
    """Node selection should persist across updates."""
```

---

## P0-7: Dark Mode Info Bar

### Problem, P0-7

Network topology info bar shows white text on white background in dark mode.

### Solution Design, P0-7

```python
# In network_visualizer.py

def get_layout(self):
    """Get network visualizer layout."""
    return html.Div([
        # Stats bar with theme-aware styling
        html.Div(
            id=f"{self.component_id}-stats-bar",
            children=[...],
            className="network-stats-bar",
        ),
        # Graph...
    ])

# Add theme callback for stats bar
@self.app.callback(
    Output(f"{self.component_id}-stats-bar", "style"),
    Input("theme-state", "data"),
)
def update_stats_bar_theme(theme):
    """Update stats bar background for dark mode."""
    if theme == "dark":
        return {
            "backgroundColor": "#343a40",
            "color": "#f8f9fa",
            "padding": "10px",
            "borderRadius": "5px",
            "marginBottom": "10px",
        }
    return {
        "backgroundColor": "#f8f9fa",
        "color": "#212529",
        "padding": "10px",
        "borderRadius": "5px",
        "marginBottom": "10px",
    }
```

### Files to Modify, P0-7

- `src/frontend/components/network_visualizer.py`
  - `get_layout()` - Add ID to stats bar container
  - `register_callbacks()` - Add theme callback
- `src/frontend/assets/styles.css` (if needed)
  - Add `.network-stats-bar` class with theme variables

### Tests to Add, P0-7

```python
# tests/unit/test_dark_mode_network.py

def test_stats_bar_dark_background():
    """Stats bar should have dark background in dark mode."""

def test_stats_bar_light_background():
    """Stats bar should have light background in light mode."""

def test_text_contrast_sufficient():
    """Text should have sufficient contrast in both modes."""
```

---

## Implementation Order

Execute in this order to minimize dependencies and maximize stability:

1. **P0-7: Dark Mode Info Bar** (Quick win, low risk)
2. **P0-1: Button State Fix** (Core interaction fix)
3. **P0-2: Apply Button** (Builds on button fix patterns)
4. **P0-3: Status Bar Updates** (Uses similar state patterns)
5. **P0-5: Pan/Lasso Tool Fix** (Foundation for P0-6)
6. **P0-6: Interaction Persistence** (Uses P0-5 patterns)
7. **P0-4: Graph Range Persistence** (Most complex, similar pattern)

---

## Verification Checklist

After Phase 0 completion:

- [ ] All 5 training buttons return to normal state after click
- [ ] Apply button enables only when parameters changed
- [ ] Status shows correct state (Running/Paused/Stopped)
- [ ] Phase shows correct phase (Output/Candidate/Idle)
- [ ] Graph zoom persists for 30+ seconds
- [ ] Pan tool actually pans
- [ ] Lasso tool actually lasso selects
- [ ] Topology interactions persist for 30+ seconds
- [ ] Dark mode info bar is readable
- [ ] All new tests pass
- [ ] Coverage >= 88%
