# Juniper-Cascor Startup Failure: Investigation, Analysis, Fix, and Validation Plan

**Date**: 2026-03-09
**Author**: Claude Code (Opus 4.6)
**Status**: Complete
**Affected Component**: juniper-cascor `./try` launcher and `src/main.py` startup flow

---

## Problem Statement

Running `./try` in juniper-cascor crashes with a `ConnectionRefusedError` → `SpiralDataProviderError` traceback. The CascadeCorrelationNetwork initializes successfully, but then the application fails when `SpiralProblem.generate_n_spiral_dataset()` attempts to fetch data from the juniper-data service at `http://localhost:8100`.

The error output spans ~80 lines of nested exception chains, making the root cause difficult to identify quickly.

---

## Root Cause Analysis

### Primary Cause
The juniper-data service is not running on `localhost:8100`. juniper-cascor has a **mandatory** dependency on juniper-data for spiral dataset generation (enforced since CAS-INT-001), but no pre-flight check exists.

### Contributing Factors

| Factor | File | Details |
|--------|------|---------|
| No pre-flight health check | `src/main.py` | Performs expensive initialization (LogConfig, SpiralProblem, CascadeCorrelationNetwork) before any attempt to reach juniper-data |
| `validate_configuration()` unused | `src/spiral_problem/data_provider.py:69` | Method exists to check connectivity but is never called in the startup flow |
| `try` script lacks dependency check | `try` (repo root) | Doesn't verify juniper-data availability before launching |
| `JUNIPER_DATA_URL` correctly set | `conf/juniper_cascor.conf:167` | URL is configured; the issue is service availability, not configuration |
| No retry or fallback | `src/spiral_problem/data_provider.py` | Single attempt, no retry, no local fallback (by design) |

### Call Chain (Failure Path)

```
try (bash) → init.conf → juniper_cascor.conf (sets JUNIPER_DATA_URL)
  → python main.py
    → main() [line 142]
      → LogConfig() [expensive init]
      → SpiralProblem() [line 236, creates CascadeCorrelationNetwork]
        → CascadeCorrelationNetwork.__init__() [expensive init]
      → sp.evaluate() [line 300]
        → solve_n_spiral_problem() [line 1269]
          → generate_n_spiral_dataset() [line 512]
            → SpiralDataProvider(url).get_spiral_dataset() [line 512]
              → _build_spiral_dataset() → client.create_dataset()
                → ConnectionRefusedError ← FAILURE POINT
```

---

## Fix Plan

### Phase 1: Investigation — Verify Environment State

1. **Confirm juniper-data is not running**: Check port 8100 for listeners
2. **Confirm JUNIPER_DATA_URL is set**: Verify `conf/juniper_cascor.conf` exports the variable
3. **Confirm `.env` file state**: Check if `JUNIPER_DATA_URL` is present in `.env`
4. **Confirm juniper-data can be started**: Verify the juniper-data `./try` script or `python -m juniper_data` works

### Phase 2: Analysis — Identify Fix Points

1. **`src/main.py`**: Add a pre-flight connectivity check for juniper-data **before** expensive initialization (before `SpiralProblem()` construction at line 236). This gives fast, clear feedback.
2. **`src/spiral_problem/spiral_problem.py`**: In `generate_n_spiral_dataset()`, call `provider.validate_configuration()` before `provider.get_spiral_dataset()` to leverage the existing health check.
3. **`try` script**: Add a lightweight HTTP health check for juniper-data before launching `python main.py`. Warn (don't block) since the user may intend to start it separately.

### Phase 3: Fix Implementation

#### Fix 3A — Pre-flight check in `main.py` (Primary Fix)

Add a connectivity check early in `main()` that:
- Reads `JUNIPER_DATA_URL` from environment
- Validates it is set (fail fast with `ConfigurationError` if missing)
- Performs an HTTP health check (`GET /v1/health`)
- On failure: logs a clear, actionable error message and exits cleanly (no traceback flood)

**Placement**: After LogConfig initialization (need logger), before `SpiralProblem()` construction (line 236). This avoids the expensive CascadeCorrelationNetwork initialization when juniper-data is unavailable.

#### Fix 3B — Validate configuration in `generate_n_spiral_dataset()` (Defense-in-depth)

After creating the `SpiralDataProvider` at line 511, call `provider.validate_configuration()` before `provider.get_spiral_dataset()`. This uses the existing method that was designed for this purpose but never wired in.

#### Fix 3C — Health check in `try` script (User Experience)

Add a `curl` check for `http://localhost:8100/v1/health` before launching the Python application. Display a warning banner if juniper-data is unreachable, directing the user to start it.

### Phase 4: Validation

1. **Without juniper-data running**: Run `./try` and verify it produces a clean, actionable error message instead of a multi-page traceback
2. **Start juniper-data**: Launch `python -m juniper_data` (or `./try` in juniper-data repo) in the JuniperData conda environment
3. **With juniper-data running**: Run `./try` in juniper-cascor and verify it proceeds past dataset generation
4. **Unit tests**: Run existing unit tests to verify no regressions: `cd src/tests && pytest unit/ -v`
5. **Integration test**: Verify the pre-flight check test coverage if applicable

---

## Files to Modify

| File | Change |
|------|--------|
| `juniper-cascor/src/main.py` | Add pre-flight juniper-data connectivity check after LogConfig init |
| `juniper-cascor/src/spiral_problem/spiral_problem.py` | Call `provider.validate_configuration()` in `generate_n_spiral_dataset()` |
| `juniper-cascor/try` | Add HTTP health check for juniper-data before launching Python |

## Files for Reference (Read-Only)

| File | Purpose |
|------|---------|
| `juniper-cascor/src/spiral_problem/data_provider.py` | Contains `validate_configuration()` method and `SpiralDataProvider` |
| `juniper-cascor/conf/juniper_cascor.conf` | Sets `JUNIPER_DATA_URL` |
| `juniper-cascor/.env` | Runtime environment (does not contain `JUNIPER_DATA_URL`) |
| `juniper-data/try` | How to start juniper-data service |

---

## Risk Assessment

- **Low risk**: All changes are additive checks that fail fast before existing behavior
- **No breaking changes**: Existing successful paths are unaffected
- **Defense-in-depth**: Multiple layers of validation (script → main → provider)
