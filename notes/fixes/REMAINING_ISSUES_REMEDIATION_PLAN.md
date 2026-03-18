# Remaining Issues Remediation Plan

**Date**: 2026-03-17
**Source**: Discovered & Remaining Issues from `DARK_MODE_AND_NETWORK_DETAILS_FIX_PLAN.md`
**Predecessor**: PR #28 (fix/canopy-dark-mode-and-network-details)
**Status**: Investigation Complete — Ready for Prioritized Execution

---

## Executive Summary

The prior fix effort (PR #28) resolved 3 user-reported issues and documented 12 additional findings across 5 categories. This investigation validates those findings against the current codebase and produces a prioritized remediation plan.

**Key discovery**: Issues 1A–1D (13 hardcoded `#f8f9fa` backgrounds on `dbc.CardHeader` components) are **NOT visible bugs**. The CSS rule in `dark_mode.css` line 67 — `.card-header { background-color: var(--bg-secondary) !important; }` — already overrides the inline styles. This eliminates 13 of the 16 documented dark mode instances from active remediation.

**Remaining actionable issues**: 7 (down from 12)

---

## Revised Issue Status

| ID | Original Status | Revised Status | Rationale |
|----|----------------|----------------|-----------|
| 1A | Open (5 CardHeaders) | **Not a Bug** | CSS `!important` already overrides inline style |
| 1B | Open (2 CardHeaders) | **Not a Bug** | CSS `!important` already overrides inline style |
| 1C | Open (2 CardHeaders) | **Not a Bug** | CSS `!important` already overrides inline style |
| 1D | Open (4 CardHeaders) | **Not a Bug** | CSS `!important` already overrides inline style |
| 1E | Open (3 tables) | **Confirmed Bug** | `html.Table` has no CSS class with `!important` override |
| 1F | Open (systemic) | **Downgraded** | CSS variables already handle CardHeaders; only non-card elements need attention |
| 2A | Documented | **Confirmed** | `src/logs` symlink broken in worktrees |
| 2B | Documented | **Confirmed** | `reports/` missing in worktrees |
| 2C | Documented | **Confirmed** | Setup procedure not updated |
| 3A | Pre-existing | **Confirmed** | 9 tests still fail on main |
| 4A | Unverified | **Resolved** | Fix verified in PR #28 (torch.cat) |
| 5A | Documented | **Confirmed** | Pre-commit hook runs all tests, fails in worktrees |

---

## Prioritized Work Units

### Work Unit 1: Worktree Developer Experience (HIGH)

**Issues**: 2A, 2B, 2C, 5A
**Effort**: Small (< 1 hour)
**Impact**: Unblocks all worktree-based development workflows

These four issues are tightly coupled — they all stem from gitignored directories not existing in worktrees, and the pre-commit hook running tests that depend on them.

#### Remediation

**2C — Update `WORKTREE_SETUP_PROCEDURE.md`**:
Add a post-setup step after Step 6 (Verify and Begin Work):
```bash
# Create gitignored directories required by the application and tests
mkdir -p logs reports
```

**2A — Fix `src/logs` symlink resilience**:
Option A (recommended): Make the logger factory create the target directory if the symlink target doesn't exist. This is a one-line fix in the logger initialization code.
Option B: Replace the symlink with a direct path computation using `pathlib.Path(__file__).parent / "logs"` or similar.

**2B — Add `.gitkeep` to `reports/`**:
Add `reports/.gitkeep` to version control so the directory is created during `git worktree add`. Remove the `reports/` entry from `.gitignore` (or adjust to `reports/*` with `!reports/.gitkeep`).

**5A — Scope pre-commit hook to unit + regression tests**:
Change `.pre-commit-config.yaml` line 268 from:
```
tests/ -q
```
to:
```
tests/unit/ tests/regression/ -q
```
Integration tests should run in CI, not as a pre-commit gate.

---

### Work Unit 2: Metrics Panel Table Dark Mode (MEDIUM-HIGH)

**Issues**: 1E (lines 1759, 1819, 1904)
**Effort**: Medium (1-2 hours)
**Impact**: Fixes visible dark mode rendering issue in Network Information: Details panel

The three `html.Table` elements in `metrics_panel.py` helper methods have hardcoded `#f8f9fa` backgrounds with no CSS class override. Unlike `dbc.CardHeader`, plain `html.Table` is not targeted by any dark mode CSS rule.

**Line 1904 is the highest priority** — it's the table inside the "Network Information: Details" panel that was fixed in PR #28 to update with live data. The panel frame is correctly themed but the table content inside it has a light background in dark mode.

#### Remediation

**Option A — CSS class approach** (preferred):
1. Add a CSS class to `dark_mode.css`:
   ```css
   .theme-table {
       background-color: var(--bg-secondary) !important;
       color: var(--text-color) !important;
   }
   .theme-table th, .theme-table td {
       border-color: var(--border-color) !important;
       color: var(--text-color) !important;
   }
   ```
2. Add `className="theme-table"` to the three `html.Table` instances
3. No callback changes needed — CSS handles everything

**Option B — Pass theme through callbacks**:
1. Add `theme` parameter to `_create_candidate_pool_display()` and `_create_network_info_table()`
2. Pass `theme` from the calling callbacks in `dashboard_manager.py`
3. Use conditional colors in the helper methods

Option A is preferred because it's consistent with the existing CardHeader pattern, requires fewer code changes, and works without modifying the callback chain.

#### Tests

- Add dark mode tests for `_create_network_info_table()` output
- Add dark mode tests for `_create_candidate_pool_display()` output
- Verify the CSS class is applied to all three tables

---

### Work Unit 3: Pre-Existing Test Failures (MEDIUM)

**Issues**: 3A (9 failing tests in `test_api_state_endpoint.py`)
**Effort**: Small-Medium (30-60 min)
**Impact**: Eliminates false negatives in test suite

#### Remediation

Fix the test fixture to properly initialize the backend before creating the `TestClient`. The `/api/state` endpoint accesses `backend.backend_type` but `backend` is `None` because the FastAPI lifespan/startup handler is never triggered.

**Approach**:
1. Add a fixture that patches `main.backend` with a mock backend object (or use the demo backend initialization)
2. Ensure the mock has `backend_type`, and the attributes accessed in `get_state()`
3. Alternative: Use `TestClient` as a context manager which triggers lifespan events

---

### Work Unit 4: Service Mode Verification (LOW)

**Issues**: 4A
**Effort**: Medium (requires live cascor backend)
**Impact**: Confirms completeness of weight data in production mode

The demo mode fix is verified and complete. Service mode delegates to `CascorServiceAdapter.get_network_data()` → `_client.get_statistics()`, which relies on the juniper-cascor backend's serialization.

#### Remediation

Add an integration test gated by `@pytest.mark.requires_cascor` that:
1. Starts a demo cascor backend (or uses a running instance)
2. Trains to produce multiple hidden units
3. Calls `get_network_data()` and verifies `hidden_weights` contains data from all units

This is low priority because the cascor backend manages its own weight serialization and is tested independently.

---

### Work Unit 5: Code Cleanup — Remove Redundant Inline Styles (LOW)

**Issues**: 1A, 1B, 1C, 1D, 1F
**Effort**: Small (< 30 min)
**Impact**: Code hygiene only — no visible change

The 13 `dbc.CardHeader` inline `backgroundColor: "#f8f9fa"` values are functionally redundant with the CSS rule. They could be removed for cleanliness, but this is optional since the CSS correctly handles dark mode already.

#### Remediation (Optional)

Remove the `backgroundColor` key from the `style` dict on all 13 `dbc.CardHeader` instances. The CSS variable `var(--bg-secondary)` provides `#f8f9fa` in light mode and `#2d2d2d` in dark mode, making the inline style unnecessary.

**Files**:
- `about_panel.py`: lines 122, 150, 193, 252, 287
- `cassandra_panel.py`: lines 229, 278
- `redis_panel.py`: lines 141, 230
- `hdf5_snapshots_panel.py`: lines 131, 200, 250, 313

---

## Implementation Order

| Priority | Work Unit | Issues | Effort | Blocking? |
|----------|-----------|--------|--------|-----------|
| 1 | Worktree Developer Experience | 2A, 2B, 2C, 5A | Small | Yes — blocks worktree workflows |
| 2 | Metrics Panel Table Dark Mode | 1E | Medium | No — cosmetic |
| 3 | Pre-Existing Test Failures | 3A | Small-Medium | No — pre-existing on main |
| 4 | Service Mode Verification | 4A | Medium | No — requires live service |
| 5 | Code Cleanup | 1A-1D, 1F | Small | No — optional hygiene |

**Recommended grouping**: Work Units 1 + 2 in a single PR (worktree infra + remaining dark mode). Work Unit 3 as a separate PR (test fixture fix). Work Units 4-5 deferred.

---

## Verification Baseline

Current test suite state (2026-03-17, post PR #28 merge):
- **1036 unit/regression tests passing**
- **96.44% coverage**
- 9 pre-existing failures in `test_api_state_endpoint.py` (not in unit/regression markers)
- 6 worktree-specific collection errors (infrastructure-dependent)
