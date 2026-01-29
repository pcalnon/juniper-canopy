# Juniper Canopy v0.25.0-alpha Release Notes

**Release Date:** 2026-01-25  
**Version:** 0.25.0-alpha  
**Codename:** Pre-Deployment Release  
**Release Type:** MINOR

---

## Overview

This release consolidates all pre-deployment work following the Phase 0-3 refactoring completion (v0.24.0). It includes critical thread safety fixes, metrics normalization for Cascor-Canopy interoperability, comprehensive API compatibility testing, and extensive pre-deployment documentation. This release prepares Juniper Canopy for production deployment alongside Juniper Cascor.

> **Status:** ALPHA – MVP Feature-complete. Integration verified. Ready for initial production deployment in BETA status.

---

## Release Summary

- **Release type:** MINOR
- **Primary focus:** Integration, Bug Fixes, Documentation, Pre-Deployment Preparation
- **Breaking changes:** No
- **Priority summary:** All P0/P1 integration issues resolved, comprehensive testing verified

---

## Features Summary

| ID            | Feature                              | Status   | Version | Phase |
| ------------- | ------------------------------------ | -------- | ------- | ----- |
| CANOPY-P1-003 | Thread-safe metrics extraction       | ✅ Done  | 0.24.6  | —     |
| CANOPY-P2-001 | Deprecation warning fix              | ✅ Done  | 0.24.4  | —     |
| INTEG-4.2     | API/Protocol compatibility tests     | ✅ Done  | 0.24.5  | —     |
| INTEG-4.3     | Metrics normalization                | ✅ Done  | 0.24.5  | —     |
| INTEG-4.1     | Backend path configuration           | ✅ Done  | 0.24.4  | —     |
| —             | Pre-deployment roadmap               | ✅ Done  | 0.24.7  | —     |
| —             | Coverage roadmap to 90%              | ✅ Done  | 0.24.7  | —     |

**Cumulative Phase Status:**

| Phase                               | Items    | Status      |
| ----------------------------------- | -------- | ----------- |
| Phase 0: Core UX Stabilization      | 11 items | ✅ Complete |
| Phase 1: High-Impact Enhancements   | 4 items  | ✅ Complete |
| Phase 2: Polish Features            | 5 items  | ✅ Complete |
| Phase 3: Advanced Features          | 7 items  | ✅ Complete |
| Pre-Deployment: Integration Fixes   | 6 items  | ✅ Complete |

---

## What's New

### Metrics Normalization (v0.24.5)

Bidirectional metrics format conversion between Cascor backend and Canopy frontend.

**Backend:**

- Added `normalize_metrics()` method to convert Cascor → Canopy format
- Added `denormalize_metrics()` method to convert Canopy → Cascor format
- Key mappings: `value_loss` ↔ `val_loss`, `value_accuracy` ↔ `val_accuracy`

**Location:** `src/backend/data_adapter.py`

**Tests Added:** 20 new unit tests in `tests/unit/backend/test_data_adapter_normalization.py`

### API Compatibility Testing (v0.24.5)

Comprehensive verification of Cascor-Canopy API contracts.

**Tests Added:** 21 new integration tests in `tests/integration/test_cascor_api_compatibility.py`

**Verification Areas:**

- Network attribute structure (input_size, output_size, hidden_units)
- Training history format (train_loss, train_accuracy, value_loss)
- Hidden unit structure (weights, bias, activation_fn)
- Topology extraction compatibility
- Metrics normalization integration

### Pre-Deployment Documentation (v0.24.7)

Comprehensive deployment preparation documentation.

**New Files:**

- `notes/PRE-DEPLOYMENT_ROADMAP.md` - Consolidated deployment checklist
  - Section 10: End-to-End Integration Analysis
  - Section 11: Continuous Profiling Infrastructure
  - Section 12: Code Coverage Roadmap to 90%
  - Section 13: Test Timeout Analysis and Resolution

**Updates:**

- `notes/INTEGRATION_ROADMAP.md` v2.1.0 - Full integration status
- `notes/VALIDATION_REPORT_2026-01-12.md` - Post-refactor validation

---

## Bug Fixes

### Thread-Safe Metrics Extraction (v0.24.6)

**Problem:** `_monitoring_loop()` reads `network.history` while training mutates it, causing intermittent exceptions or inconsistent reads.

**Root Cause:** Race condition between monitoring thread and training thread accessing shared network.history data.

**Solution:**

- Added `self.metrics_lock = threading.Lock()` for thread-safe metrics extraction
- Updated `_extract_current_metrics()` to use lock when accessing network.history
- Added defensive copying of history lists while holding lock
- Added exception handling for concurrent modification edge cases

**Files:** `src/backend/cascor_integration.py` (lines 117-121, 765-789)

### asyncio.iscoroutinefunction Deprecation (v0.24.4)

**Problem:** `asyncio.iscoroutinefunction` is deprecated and slated for removal in Python 3.16.

**Solution:** Replaced `asyncio.iscoroutinefunction()` with `inspect.iscoroutinefunction()`.

**Files:** `src/tests/unit/test_main_coverage_extended.py` (line 437)

### Missing pytest-mock Dependency (v0.24.2)

**Problem:** 32 tests failed with `fixture 'mocker' not found` error.

**Root Cause:** `pytest-mock` package missing from JuniperCanopy conda environment.

**Solution:** Added `pytest-mock=3.15.1` to `conda_environment.yaml`.

**Files:** `conda_environment.yaml`, affects `test_dashboard_manager.py` handler tests

### Backend Path Configuration (v0.24.4)

**Problem:** Hardcoded backend path limited deployment flexibility.

**Solution:** Changed to environment variable with default fallback: `${CASCOR_BACKEND_PATH:../JuniperCascor/juniper_cascor}`

**Files:** `conf/app_config.yaml`

---

## Improvements

### Test Coverage (v0.24.0 → v0.25.0)

Significant test additions for integration verification:

| Component                          | v0.24.0 | v0.25.0 | Change    |
| ---------------------------------- | ------- | ------- | --------- |
| data_adapter.py                    | 100%    | 100%    | +20 tests |
| test_cascor_api_compatibility.py   | —       | New     | +21 tests |
| test_data_adapter_normalization.py | —       | New     | +20 tests |

### Test Count Growth

| Version       | Tests | Change |
| ------------- | ----- | ------ |
| 0.24.0-alpha  | 2908  | —      |
| 0.24.1        | 2908  | +0     |
| 0.24.2        | 2903  | -5*    |
| 0.24.5        | 2944  | +41    |
| 0.25.0-alpha  | 2983  | +39    |

**Total new tests since v0.24.0:** 75 tests

*Note: Minor test adjustment in 0.24.2 due to environment normalization

### Documentation

- Comprehensive pre-deployment roadmap with prioritized issues
- Integration analysis with all blockers resolved
- Coverage improvement roadmap targeting 90%
- Test timeout analysis and resolution documentation

---

## API Changes

### New Methods

| Method                  | Module          | Description                         |
| ----------------------- | --------------- | ----------------------------------- |
| `normalize_metrics()`   | data_adapter.py | Convert Cascor → Canopy metric keys |
| `denormalize_metrics()` | data_adapter.py | Convert Canopy → Cascor metric keys |

### Metrics Key Mapping

| Cascor Key       | Canopy Key       | Direction      |
| ---------------- | ---------------- | -------------- |
| `value_loss`     | `val_loss`       | Bidirectional  |
| `value_accuracy` | `val_accuracy`   | Bidirectional  |
| `loss`           | `train_loss`     | Legacy format  |
| `accuracy`       | `train_accuracy` | Legacy format  |

---

## Test Results

### Test Suite

| Metric            | Result              |
| ----------------- | ------------------- |
| **Tests passed**  | 2942                |
| **Tests skipped** | 41                  |
| **Tests failed**  | 0                   |
| **Runtime**       | ~112 seconds        |
| **Coverage**      | 94% overall         |

### Coverage Details

| Component               | Coverage | Target | Status       |
| ----------------------- | -------- | ------ | ------------ |
| cascor_integration.py   | 100%     | 95%    | ✅ Exceeded  |
| data_adapter.py         | 100%     | 95%    | ✅ Exceeded  |
| websocket_manager.py    | 100%     | 95%    | ✅ Exceeded  |
| statistics.py           | 100%     | 95%    | ✅ Exceeded  |
| constants.py            | 100%     | 95%    | ✅ Exceeded  |
| dashboard_manager.py    | 95%      | 95%    | ✅ Met       |
| training_monitor.py     | 95%      | 95%    | ✅ Met       |
| hdf5_snapshots_panel.py | 95%      | 95%    | ✅ Met       |
| demo_mode.py            | 94%      | 95%    | ⚠️ Near      |
| main.py                 | 84%      | 95%    | ⚠️ Near*     |

*main.py remaining uncovered lines require real CasCor backend or uvicorn runtime

---

## Upgrade Notes

This is a backward-compatible release. No migration steps required. All changes are additive.

```bash
# Update and verify
git pull origin main
./demo

# Run test suite
cd src && pytest tests/ -v

# Verify API compatibility (optional, requires Cascor backend)
export CASCOR_BACKEND_AVAILABLE=1
pytest tests/integration/test_cascor_api_compatibility.py -v
```

### Environment Update

If recreating the conda environment:

```bash
conda env update -f conda_environment.yaml
```

New dependency: `pytest-mock=3.15.1`

---

## Known Issues

- **main.py coverage at 84%:** Remaining uncovered lines require real CasCor backend or uvicorn runtime for testing. Not a functional issue.
- **Module naming collision:** Canopy's `constants.py` may shadow Cascor's `constants/` package. Workaround: `CascorIntegration` handles path ordering automatically.

---

## What's Next

### Planned for v0.26.0

- Production deployment verification
- Performance optimization for large networks
- Profiling infrastructure implementation

### Coverage Goals

- Overall: 94% → 90%+ (current target met)
- `main.py`: 84% → 95% (requires backend testing)

### Roadmap

See [PRE-DEPLOYMENT_ROADMAP.md](../PRE-DEPLOYMENT_ROADMAP.md) for:

- Multiprocessing timeout hardening
- Profiling infrastructure phases
- Coverage improvement plan

---

## Contributors

- Paul Calnon
- Development Team

---

## Version History

| Version      | Date       | Description                                            |
| ------------ | ---------- | ------------------------------------------------------ |
| 0.24.0-alpha | 2026-01-11 | Post-refactor verification, documentation templates    |
| 0.24.1       | 2026-01-12 | Post-refactor validation                               |
| 0.24.2       | 2026-01-12 | Missing pytest-mock dependency fix                     |
| 0.24.3       | 2026-01-20 | Deprecation warning documentation                      |
| 0.24.4       | 2026-01-21 | Backend path config, asyncio deprecation fix           |
| 0.24.5       | 2026-01-22 | Metrics normalization, API compatibility tests         |
| 0.24.6       | 2026-01-24 | Thread-safe metrics extraction                         |
| 0.24.7       | 2026-01-24 | Integration analysis, profiling refs, coverage roadmap |
| 0.25.0-alpha | 2026-01-25 | Pre-deployment release consolidation                   |

---

## Links

- [Full Changelog](../../CHANGELOG.md)
- [Pre-Deployment Roadmap](../PRE-DEPLOYMENT_ROADMAP.md)
- [Integration Roadmap](../INTEGRATION_ROADMAP.md)
- [Validation Report](../VALIDATION_REPORT_2026-01-12.md)
- [Pull Request Details](../pull_requests/PR_DESCRIPTION_RELEASE_v0.25.0_2026-01-25.md)
- [Previous Release: v0.24.0-alpha](RELEASE_NOTES_v0.24.0-alpha.md)

---
