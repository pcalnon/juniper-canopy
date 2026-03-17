# Canopy UI Regressions & Enhancements Plan

**Date**: 2026-03-16

---

## Items

### Item 1: Metrics Tab Layout Toolbar Dark Mode (Regression)

**Root Cause**: Hardcoded inline `backgroundColor: "#f8f9fa"` on the layout controls container in `metrics_panel.py` line 221. The `dark_mode.css` has zero rules targeting this element, and inline styles take precedence over CSS class selectors.

**Fix**: Replace the hardcoded background color with CSS variable `var(--bg-secondary)`, and add a CSS class for the layout controls container that dark mode can target. Also fix hardcoded colors on the status text and divider.

**Files**: `src/frontend/components/metrics_panel.py`, `src/frontend/assets/dark_mode.css`

### Item 2: Decision Boundary Tab Stale Display (Regression)

**Finding**: The boundary already refreshes every 5 seconds via `slow-update-interval` while the tab is active. However, there's no manual refresh button and no visual feedback when data refreshes.

**Fix**: Add a "Refresh" button to the decision boundary tab header area. Wire it to force an immediate API re-fetch. Add a brief "Refreshing..." status flash for visual feedback.

**Files**: `src/frontend/components/decision_boundary.py`, `src/frontend/dashboard_manager.py`

### Item 3: Candidate Pool History Display (Regression)

**Current state**: Historical pools section only renders if history has >1 entries and only shows during active-to-inactive transitions. "No active candidate pool" shown when inactive.

**Fix**: Always display historical candidate pools regardless of current status. Each entry should be expandable. Display a user-configurable number of previous pools (default 20).

**Files**: `src/frontend/components/metrics_panel.py`

### Item 4: Network Information Details Expandable Indicator (Enhancement)

**Current state**: Plain H6 text with `cursor: pointer` but no visual indicator.

**Fix**: Add toggle arrow (▶/▼), hover background change, and CSS transitions. Follow the existing pattern from metrics_panel.py's candidate pool collapsible.

**Files**: `src/frontend/dashboard_manager.py`, `src/frontend/assets/dark_mode.css`

### Item 5: Metrics Display Mode Selection (Enhancement)

**Current state**: Fixed 100-epoch sliding window hardcoded in `dashboard_manager.py` API call.

**Fix**: Add radio button group for display mode: Full History, Variable Window (user-defined width), Between Hidden Units. Add state store for mode selection. Modify data fetching and plot rendering to support each mode.

**Files**: `src/frontend/components/metrics_panel.py`, `src/frontend/dashboard_manager.py`, `src/main.py`, `src/canopy_constants.py`

---

## Implementation Order

1. Item 1 (dark mode toolbar) — CSS fix, minimal risk
2. Item 4 (expandable indicator) — small UI change
3. Item 2 (boundary refresh button) — small addition
4. Item 3 (candidate pool history) — moderate
5. Item 5 (metrics display modes) — most complex
