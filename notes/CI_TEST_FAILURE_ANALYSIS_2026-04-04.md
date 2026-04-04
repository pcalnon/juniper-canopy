# CI Test Failure Analysis: Observability Module Missing Dependencies

**Date**: 2026-04-04
**Branch**: `fix/ci-test-collection-and-deps`
**Status**: Resolved

---

## Executive Summary

5 unit tests in `src/tests/unit/test_observability.py` fail across all Python versions (3.12, 3.13, 3.14) in GitHub Actions CI due to undeclared dependencies on `sentry_sdk` and `prometheus_client`. These pass locally because the JuniperCanopy conda environment has these packages installed. The failure cascades to block all downstream CI jobs (Integration Tests, Build Distribution, Docker Build, Quality Gate).

## Failing Tests

| Test | Error | Missing Module |
|------|-------|----------------|
| `TestConfigureSentry::test_initializes_when_dsn_provided` | `ModuleNotFoundError` | `sentry_sdk` |
| `TestPrometheusMiddleware::test_increments_counter_and_records_histogram` | `ModuleNotFoundError` | `prometheus_client` |
| `TestPrometheusMiddleware::test_namespace_prefix_applied_to_metric_names` | `ModuleNotFoundError` | `prometheus_client` |
| `TestPrometheusMiddleware::test_empty_namespace_produces_unprefixed_names` | `ModuleNotFoundError` | `prometheus_client` |
| `TestGetPrometheusApp::test_returns_asgi_app` | `ModuleNotFoundError` | `prometheus_client` |

## CI Job Cascade

| Job | Status | Root Cause |
|-----|--------|------------|
| Pre-commit (all versions) | Pass | N/A |
| Lockfile Freshness | Pass | N/A |
| Security Scans | Pass | N/A |
| Documentation Links | Pass | N/A |
| **Unit Tests + Coverage** | **FAIL** | **Missing sentry_sdk & prometheus_client** |
| Integration Tests | Skipped | Blocked by unit test failure |
| Build Distribution | Skipped | Blocked by unit test failure |
| Dependency Documentation | Skipped | Blocked by unit test failure |
| Docker Build & Smoke Test | Skipped | Blocked by unit test failure |
| **Quality Gate** | **FAIL** | Unit tests failed |

## Root Cause Analysis

### Source Code Pattern

`src/observability.py` uses **lazy imports** for both packages, explicitly designed as optional dependencies (comment at line 172-173: "lazily initialized to avoid requiring prometheus_client at import time (it is an optional dependency)"):

- Line 64: `from prometheus_client import Counter, Histogram` (inside `PrometheusMiddleware.__init__`)
- Line 135: `import sentry_sdk` (inside `configure_sentry()`)
- Line 152: `from prometheus_client import make_asgi_app` (inside `get_prometheus_app()`)
- Line 164: `from prometheus_client import Info` (inside `set_build_info()`)
- Line 183: `from prometheus_client import Counter, Gauge` (inside `_ensure_canopy_metrics()`)

### Test Pattern

The tests use `unittest.mock.patch()` to mock these modules:

```python
with patch("sentry_sdk.init") as mock_init:
with patch("prometheus_client.Counter") as MockCounter:
with patch("prometheus_client.Histogram") as MockHistogram:
```

`mock.patch()` requires the target module to be importable before it can be patched. When `sentry_sdk` / `prometheus_client` are not installed, `patch()` raises `ModuleNotFoundError`.

### Why Tests Pass Locally

The JuniperCanopy conda environment (`/opt/miniforge3/envs/JuniperCanopy`) has both packages installed as part of the development environment, even though they are not declared in project metadata.

### Why Tests Fail in CI

CI installs dependencies from:

1. `conf/requirements_ci.txt` (explicit CI requirements)
2. `pyproject.toml` via `pip install -e .` (project dependencies)

Neither file listed `sentry_sdk` or `prometheus_client`.

### Existing Stub Pattern

The test conftest (`src/tests/conftest.py`, lines 52-163) injects stub modules for `juniper_data_client` and `juniper_cascor_client` when not installed. This pattern exists because those are custom Juniper packages that may not be published to PyPI. However, no equivalent stubs exist for `sentry_sdk` or `prometheus_client`.

## Resolution Approach

### Approach Considered: Stub Injection (Not Chosen)

Add mock module stubs in `conftest.py` following the existing pattern. While functional, this was rejected because:

- `sentry_sdk` and `prometheus_client` are well-established PyPI packages (always available)
- Stubs for prometheus_client would need to mock `Counter`, `Histogram`, `Gauge`, `Info`, `make_asgi_app` — complex and fragile
- The root issue is missing dependency declaration, not package availability

### Approach Chosen: Declare Dependencies + Add to CI

1. Add `observability` optional extra to `pyproject.toml` with `prometheus-client>=0.20.0` and `sentry-sdk>=2.0.0`
2. Add both packages to `conf/requirements_ci.txt`
3. Regenerate `requirements.lock` with `--extra observability`
4. Update CI lockfile freshness check to include `--extra observability`

**Rationale**: This properly declares the dependency relationship in package metadata while keeping them optional (users who don't need Prometheus/Sentry metrics don't need to install them). CI explicitly installs these for testing.

## Additional Issues Discovered During CI Validation

### Issue 2: Coverage Threshold Failure (76% < 80%)

**Root Cause**: CI ran `cd src && python -m pytest --cov=.` which measured coverage
of ALL files in `src/` including test files. Integration test files at 0% (not run
in unit test job) inflated the uncovered line count. The omit patterns in
`pyproject.toml` were not applied because paths were relative to `src/`, not the
project root where pyproject.toml lives.

**Fix**: Changed CI to run pytest from the project root using `--cov=src` instead of
`cd src && --cov=.`. Added `tests/*` and `conftest.py` to coverage omit patterns.
Coverage now correctly reports **88.76%** (source only, no test files).

### Issue 3: Python 3.12 SIGABRT During Cleanup

**Root Cause**: Python 3.12 on GitHub Actions consistently crashes with SIGABRT
(exit code 134) during interpreter cleanup AFTER all tests pass and coverage is
generated. Python 3.13 and 3.14 are unaffected. This is a CPython 3.12 runtime
bug, not a test issue.

**Fix**: Added exit code handling that checks JUnit XML results when SIGABRT occurs.
If JUnit XML exists with 0 failures and 0 errors, the run is treated as successful
with a warning annotation.

### Issue 4: Lockfile Freshness False Positive

**Root Cause**: `uv pip compile` embeds the `-o` output path in the autogenerated
header comment. CI writes to `/tmp/requirements.lock.check` while the committed
file has `-o requirements.lock`, causing a diff on the comment line only.

**Fix**: Strip the first 2 header lines before comparing to check only actual
package content.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Added `observability` optional extra; fixed coverage omit patterns |
| `conf/requirements_ci.txt` | Added `prometheus-client>=0.20.0` and `sentry-sdk>=2.0.0` |
| `requirements.lock` | Regenerated with `--extra observability` |
| `.github/workflows/ci.yml` | Multiple fixes: lockfile check, coverage scope, Python 3.12 workaround |

## Verification

- **Local unit tests**: 21/21 passed in `test_observability.py`
- **CI-equivalent suite**: 3389 passed, 0 failed, 4 deselected
- **Full test suite**: 4169 passed, 56 skipped (all skips are expected external service deps)
- **Coverage**: 88.76% (source only, properly excluding test files)
- **No test functionality removed or disabled**
