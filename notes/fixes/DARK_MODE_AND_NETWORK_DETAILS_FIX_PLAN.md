# Dark Mode & Network Details Fix Plan

**Date**: 2026-03-17
**Branch**: `fix/canopy-dark-mode-and-network-details`
**Status**: Complete

---

## Overview

Three related frontend display issues in juniper-canopy:

1. **Network Topology Node Detail** — dark mode not honored (white background, black text)
2. **Dataset Visualization Summary** — dark mode background not honored (white background, text correct)
3. **Network Information: Details** — dropdown content not updating during training

---

## Issue 1: Network Topology Node Detail Dark Mode

### Problem

When a node is selected on the Network Topology tab, a "node detail header" appears between the summary heading and the plot title. This panel does not respond to dark mode — it always renders with a light blue background (`#e3f2fd`) and hardcoded light-mode text colors.

### Root Cause

**File**: `src/frontend/components/network_visualizer.py`

1. **Initial style (lines 187-197)**: The `selection-info` div has hardcoded `backgroundColor: "#e3f2fd"` with no theme awareness
2. **Callback (lines 432-519)**: `handle_node_selection` does NOT include `Input("theme-state", "data")` — it never receives theme changes
3. **Hardcoded styles (lines 452-460)**: `base_style` uses `#e3f2fd` background and `#90caf9` border unconditionally
4. **Text colors (lines 480, 508, 512)**: Inline styles use `#666` and `#888` (dark gray) — invisible on dark backgrounds

### Working Reference

The stats bar on the same tab DOES handle dark mode correctly via a dedicated callback (lines 417-430):

```python
@app.callback(
    Output(f"{self.component_id}-stats-bar", "style"),
    Input("theme-state", "data"),
)
def update_stats_bar_theme(theme):
    is_dark = theme == "dark"
    return {
        "backgroundColor": "#343a40" if is_dark else "#f8f9fa",
        "color": "#f8f9fa" if is_dark else "#212529",
        ...
    }
```

### Fix Plan

**Approach**: Add `State("theme-state", "data")` to `handle_node_selection` callback and compute theme-aware styles.

Using `State` instead of `Input` because we don't want the callback to fire on theme change alone — only when a node selection event occurs. A separate theme callback will handle re-theming when the user toggles dark mode while a selection is already visible.

**Changes**:

1. **Modify `handle_node_selection` callback** (line 432-519):
   - Add `State("theme-state", "data")` parameter
   - Build `base_style` with conditional colors:
     - Light: `backgroundColor: "#e3f2fd"`, `border: "1px solid #90caf9"`
     - Dark: `backgroundColor: "#1a3a5c"`, `border: "1px solid #2c5282"`
   - Build text colors conditionally:
     - Light: `#666`, `#888`
     - Dark: `#adb5bd`, `#9ca3af`

2. **Add new theme callback** for `selection-info` style:
   - `Input("theme-state", "data")`, `State(f"{self.component_id}-selection-info", "style")`
   - When theme changes, update background/border colors while preserving display state

### Color Palette

| Element | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Selection background | `#e3f2fd` | `#1a3a5c` |
| Selection border | `#90caf9` | `#2c5282` |
| Primary text | inherited | inherited |
| Secondary text | `#666` | `#adb5bd` |
| Hint text | `#888` | `#9ca3af` |

---

## Issue 2: Dataset Visualization Summary Dark Mode

### Problem

On the Dataset View tab, the summary header (showing Samples, Features, Classes, Balance) between the tab heading and the scatter plot has a white/light gray background (`#f8f9fa`) that doesn't change in dark mode. The text within the section IS correct (white in dark mode via CSS).

### Root Cause

**File**: `src/frontend/components/dataset_plotter.py`

1. **No ID on the div (lines 118-149)**: The stats summary div has no `id` attribute, so no callback can target it
2. **Hardcoded background (line 146)**: `backgroundColor: "#f8f9fa"` never changes
3. **No theme callback**: Unlike `network_visualizer.py`'s `update_stats_bar_theme`, there is no equivalent for the dataset plotter

### Working Reference

The text IS correct because `dark_mode.css` applies `color` to text elements globally, but the `backgroundColor` is an inline style which takes precedence over CSS, so the CSS cannot override it.

### Fix Plan

**Changes**:

1. **Add ID to the stats div** (line 118):
   - `id=f"{self.component_id}-stats-summary"`

2. **Add theme callback** in `register_callbacks`:
   ```python
   @app.callback(
       Output(f"{self.component_id}-stats-summary", "style"),
       Input("theme-state", "data"),
   )
   def update_stats_summary_theme(theme):
       is_dark = theme == "dark"
       return {
           "marginBottom": "15px",
           "padding": "10px",
           "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
           "color": "#e9ecef" if is_dark else "#212529",
           "borderRadius": "3px",
       }
   ```

### Color Palette

| Element | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Background | `#f8f9fa` | `#2d2d2d` |
| Text color | `#212529` | `#e9ecef` |

---

## Issue 3: Network Information Details Not Updating

### Problem

The "Network Information: Details" collapsible section in the left sidebar shows only initial values from network creation. It never updates as training progresses and hidden units are added.

### Root Cause

**File**: `src/main.py` (lines 555-595)

The `/api/network/stats` endpoint has a critical bug in demo mode — it only captures the **first** hidden unit's weights:

```python
hidden_weights=(network.hidden_units[0]["weights"] if network.hidden_units else None),
```

This means:
- When no hidden units exist yet: `hidden_weights=None` (correct initially)
- After 1+ hidden units added: only first unit's weights captured, all subsequent units ignored
- Weight statistics are incomplete and do not reflect topology changes

### Investigation Detail

**Callback**: `dashboard_manager.py` lines 726-732 — polls every 5s via `slow-update-interval` (working correctly)

**Handler**: `dashboard_manager.py` lines 1170-1186 — calls `/api/network/stats` and passes result to `_create_network_info_table` (working correctly)

**API Endpoint**: `main.py` lines 555-595 — creates `DataAdapter` and calls `get_network_statistics()`:
- Demo mode (line 575): `network.hidden_units[0]["weights"]` — **only first hidden unit**
- Service mode (lines 583-593): uses `network_data.get("hidden_weights")` — depends on service adapter

**Data Adapter**: `backend/data_adapter.py` lines 363-450 — `get_network_statistics()` method combines all weight tensors and computes statistics. The method itself is correct; it receives whatever weights are passed to it.

### Fix Plan

**Changes**:

1. **Fix demo mode hidden weights collection** (`src/main.py`, line 575):
   - Collect ALL hidden unit weights, not just index [0]
   - Concatenate all hidden unit weight arrays into a single array
   ```python
   # Before:
   hidden_weights=(network.hidden_units[0]["weights"] if network.hidden_units else None),

   # After:
   hidden_weights=(
       np.concatenate([hu["weights"] for hu in network.hidden_units])
       if network.hidden_units else None
   ),
   ```

2. **Verify service mode** (`src/main.py`, lines 583-593):
   - Check that `backend._adapter.get_network_data()` returns complete hidden weights
   - This is likely already correct since it gets data from the CasCor backend directly

### Data Flow (After Fix)

```
slow-update-interval (5s) → callback → _update_network_info_details_handler()
→ GET /api/network/stats → DataAdapter.get_network_statistics(all_weights)
→ _create_network_info_table(stats) → UI update
```

---

## Test Plan

### New Tests Required

#### 1. Dark Mode Node Detail Tests (`test_network_visualizer_callbacks.py`)

- `test_handle_node_selection_dark_mode_style`: Verify dark mode background/border colors when selecting a node with theme="dark"
- `test_handle_node_selection_light_mode_style`: Verify light mode colors preserved
- `test_selection_info_theme_callback_dark`: Verify the theme callback updates selection-info style for dark mode
- `test_selection_info_theme_callback_light`: Verify light mode styling

#### 2. Dark Mode Dataset Summary Tests (`test_dataset_plotter.py`)

- `test_stats_summary_has_id`: Verify the stats summary div has the expected ID
- `test_stats_summary_theme_callback_dark`: Verify dark mode background color
- `test_stats_summary_theme_callback_light`: Verify light mode background color

#### 3. Network Stats Update Tests

- `test_network_stats_all_hidden_weights`: Verify `/api/network/stats` captures all hidden unit weights
- `test_network_stats_no_hidden_units`: Verify correct handling when no hidden units exist
- `test_network_stats_multiple_hidden_units`: Verify weight statistics change after adding hidden units

#### 4. Regression Tests

- `test_dark_mode_all_info_panels_themed`: Verify all info/summary panels respond to dark mode
- `test_network_details_updates_during_training`: End-to-end test verifying the details section changes during demo training

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/frontend/components/network_visualizer.py` | Add theme awareness to node selection callback, add theme callback for selection-info |
| `src/frontend/components/dataset_plotter.py` | Add ID to stats div, add theme callback |
| `src/main.py` | Fix hidden weights collection in `/api/network/stats` demo mode |
| `src/tests/unit/frontend/test_network_visualizer_callbacks.py` | Add dark mode node selection tests |
| `src/tests/unit/test_dataset_plotter.py` | Add dark mode stats summary tests |
| `src/tests/unit/test_network_info_enhancements.py` | Add network stats update tests |
| `src/tests/regression/test_dark_mode_info_panels.py` | New regression test file |

---

## Implementation Order

1. Fix 1: Network topology node detail dark mode
2. Fix 2: Dataset visualization summary dark mode
3. Fix 3: Network info details not updating
4. Add tests for all fixes
5. Run full test suite
6. Final audit for similar issues

---

## Analysis & Investigation Log

### Investigation Phase (2026-03-17)

**Sub-agent 1 — Network Topology Dark Mode**:
- Identified `network_visualizer.py` as the source
- Found hardcoded `#e3f2fd` background at lines 187-197 and 452-460
- Found missing `theme-state` input in `handle_node_selection` callback
- Found hardcoded text colors at lines 480, 508, 512
- Confirmed `update_stats_bar_theme` (lines 417-430) as working reference pattern

**Sub-agent 2 — Dataset Summary Dark Mode**:
- Identified `dataset_plotter.py` as the source
- Found missing ID on stats div (lines 118-149)
- Found hardcoded `#f8f9fa` at line 146
- Confirmed text is correct via CSS global rules, but backgroundColor inline style overrides CSS

**Sub-agent 3 — Network Details Not Updating**:
- Identified `main.py` `/api/network/stats` endpoint (lines 555-595) as the root cause
- Found `hidden_units[0]` bug at line 575 — only first hidden unit captured
- Confirmed polling callback and handler are working correctly
- Confirmed `_create_network_info_table` in `metrics_panel.py` (lines 1835-1908) is correct

**Sub-agent 4 — Backend API Deep Dive**:
- Confirmed endpoint creates fresh `DataAdapter` on each call (no caching issue)
- Confirmed `get_network_statistics()` in `data_adapter.py` correctly computes stats from provided weights
- Identified the single-unit indexing as the sole blocker

**Sub-agent 5 — Test Suite Analysis**:
- Found existing test patterns in `test_network_visualizer_callbacks.py`, `test_dataset_plotter.py`, `test_network_info_enhancements.py`
- Found existing dark mode integration tests in `tests/integration/test_dark_mode.py`
- Documented callback simulation and mock patterns used across the suite

### Implementation Phase (2026-03-17)

**Fix 1 — Network Topology Node Detail Dark Mode**:
- Modified `handle_node_selection` callback in `network_visualizer.py`:
  - Added `State("theme-state", "data")` to callback inputs
  - Built `base_style` with conditional colors based on `is_dark`
  - Added theme-aware text colors (`secondary_color`, `hint_color`)
- Added new `update_selection_info_theme` callback for live theme switching
- Updated 3 existing tests to pass `theme` parameter

**Fix 2 — Dataset Summary Dark Mode**:
- Added `id=f"{self.component_id}-stats-summary"` to the stats div in `dataset_plotter.py`
- Added `update_stats_summary_theme` callback with dark/light color switching

**Fix 3 — Network Info Details Not Updating**:
- Fixed `main.py` `/api/network/stats` endpoint:
  - Changed `network.hidden_units[0]["weights"]` to `torch.cat([hu["weights"] for hu in network.hidden_units])`
  - Now captures weights from ALL hidden units

### Test Results (2026-03-17)

- 11 new regression tests added in `tests/regression/test_dark_mode_info_panels.py`
- 3 existing tests updated for new `theme` parameter
- Full suite: **1036 passed, 0 failures**

### Final Audit (2026-03-17)

Audit of all frontend components for remaining hardcoded background colors found additional instances in secondary panels (out of scope for this fix):

| File | Instances | Notes |
|------|-----------|-------|
| `about_panel.py` | 5 CardHeader `#f8f9fa` | Static informational panel |
| `cassandra_panel.py` | 2 CardHeader `#f8f9fa` | Database monitoring panel |
| `redis_panel.py` | 2 CardHeader `#f8f9fa` | Cache monitoring panel |
| `hdf5_snapshots_panel.py` | 4 CardHeader `#f8f9fa` | Snapshot management panel |
| `metrics_panel.py` | 3 helper method `#f8f9fa` | Table backgrounds in `_create_candidate_pool_display` and `_create_network_info_table` |

These are cosmetic issues in secondary panels and do not affect the three primary user-reported issues. They are documented here for future remediation.
