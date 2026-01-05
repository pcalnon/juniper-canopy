# Fix: DEFAULT_SCALE NameError in NetworkVisualizer

**Date:** 2025-12-13  
**Status:** Resolved  
**Severity:** Critical (blocked all test collection)

## Issue Summary

All tests were failing to collect due to a `NameError` in `network_visualizer.py`.

### Error Message

```bash
NameError: name 'DEFAULT_SCALE' is not defined
```

### Root Cause

In `src/frontend/components/network_visualizer.py` at line 578, the method `_calculate_layout()` used `DEFAULT_SCALE` as a default parameter value, but this constant was never imported or defined in the file.

The constant exists in `constants.py` as `DashboardConstants.DEFAULT_SCALE`, but only `DashboardConstants` was imported—not the individual constant.

### Code Before Fix

```python
def _calculate_layout(
    self,
    G: nx.DiGraph,
    layout_type: str,
    n_input: int,
    n_hidden: int,
    n_output: int,
    scale: float = DEFAULT_SCALE,  # NameError here
) -> Dict[str, Tuple[float, float]]:
```

### Fix Applied

Changed the default parameter to reference the constant through its class:

```python
def _calculate_layout(
    self,
    G: nx.DiGraph,
    layout_type: str,
    n_input: int,
    n_hidden: int,
    n_output: int,
    scale: float = DashboardConstants.DEFAULT_SCALE,  # Fixed
) -> Dict[str, Tuple[float, float]]:
```

## Impact

- **Before fix:** 20 test collection errors, 0 tests running
- **After fix:** 1213 tests passed, 37 skipped, 84% coverage

## Files Modified

- `src/frontend/components/network_visualizer.py` (line 578)

## Verification

```bash
cd src
pytest tests/ -v --tb=short
# Result: 1213 passed, 37 skipped
```

## Prevention

This type of error can be caught by:

1. **Pre-commit hooks with mypy**: Type checking would catch undefined names
2. **CI syntax validation**: `python -m py_compile` catches basic errors
3. **Import testing**: Ensure all modules can be imported before running tests

## Related Documentation

- [Constants Guide](../docs/CONSTANTS_GUIDE.md) - How to properly use constants
- [AGENTS.md](../AGENTS.md) - Development guidelines and code style

---

## Test Suite Expansion - 2025-12-13

### Summary

Following the critical bug fix, the test suite was significantly expanded to reach 90% coverage.

#### Coverage Improvement

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Overall Coverage | 84% | 90% | +6% |
| Total Tests | 1213 | 1666 | +453 |
| Tests Passing | 1213 | 1666 | +453 |

#### New Test Files Created

| Test File | Tests | Target Component | Coverage Impact |
|-----------|-------|------------------|-----------------|
| `test_callback_context_coverage.py` | 29 | `callback_context.py` | 49% → 100% |
| `test_dashboard_helpers_coverage.py` | 48 | `dashboard_manager.py` | 51% → 67% |
| `test_network_visualizer_layout_coverage.py` | 43 | `network_visualizer.py` | 59% → 71% |
| `test_metrics_panel_helpers_coverage.py` | 74 | `metrics_panel.py` | 57% → 67% |
| `test_main_api_coverage.py` | 36 | `main.py` | 67% → 79% |
| `test_demo_mode_comprehensive.py` | 72 | `demo_mode.py` | 81% → 94% |
| `test_websocket_comprehensive.py` | 51 | `websocket_manager.py` | 76% → 94% |
| `test_config_manager_comprehensive.py` | 42 | `config_manager.py` | 79% → 95% |
| `test_cascor_integration_comprehensive.py` | 49 | `cascor_integration.py` | 76% → 95% |
| `test_base_component_coverage.py` | 9 | `base_component.py` | 81% → 92% |

#### Component Coverage Summary

| Component | Before | After | Status |
|-----------|--------|-------|--------|
| `callback_context.py` | 49% | 100% | ✅ |
| `config_manager.py` | 79% | 95% | ✅ |
| `cascor_integration.py` | 76% | 95% | ✅ |
| `demo_mode.py` | 81% | 94% | ✅ |
| `websocket_manager.py` | 76% | 94% | ✅ |
| `base_component.py` | 81% | 92% | ✅ |
| `main.py` | 67% | 79% | ⚠️ (Dash integration) |
| `dashboard_manager.py` | 51% | 67% | ⚠️ (Dash integration) |
| `metrics_panel.py` | 57% | 67% | ⚠️ (Dash integration) |
| `network_visualizer.py` | 59% | 71% | ⚠️ (Dash integration) |

#### Notes

The Dash UI components (dashboard_manager, metrics_panel, network_visualizer) remain at 67-71% because:

1. Dash callbacks require a running Dash application context
2. Integration tests would be needed for full coverage
3. The helper methods and logic are now well-tested

#### Verification, Test Suite Expansion

```bash
cd src
pytest tests/ --cov=. --cov-report=term
# Result: 1666 passed, 37 skipped, 90% coverage
```
