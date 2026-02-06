# ADR-001: Valid Test Skips Documentation

**Status:** Accepted
**Date:** 2026-02-04
**Author:** Test Suite Enhancement Project

## Context

During the Test Suite CI/CD Enhancement project (Phase 3, Epic 3.2), we identified several tests that use `@pytest.mark.skip` or `pytest.skip()` unconditionally. These skips fall into two categories:

1. **Invalid skips** - Tests that should be conditionally skipped based on environment
2. **Valid skips** - Tests that are correctly skipped due to technical limitations

This ADR documents the **valid skips** that should remain in the codebase with proper documentation.

## Decision

The following test skips are considered valid and should NOT be converted to conditional skips:

### SK-001: VERBOSE Custom Logging Level

**File:** `tests/unit/test_logger_coverage.py:134`
**Test:** `test_verbose_logging`
**Reason:** VERBOSE is a custom logging level not part of Python's standard logging module

The CascorLogger implements a custom VERBOSE level (15, between DEBUG and INFO). The test is skipped because the standard logging module's `getLevelName()` doesn't recognize custom levels without additional setup. The VERBOSE level is tested indirectly through other logger tests.

**Alternative:** Could implement custom level registration in test setup, but this adds complexity for minimal value.

### SK-002 & SK-003: HDF5 Global Directory Patching

**File:** `tests/integration/test_hdf5_snapshots_api.py:236,244`
**Tests:** `test_lists_real_hdf5_files`, `test_ignores_non_hdf5_files`
**Reason:** Requires patching global `_snapshots_dir` which is complex in demo mode

These tests are designed to verify real HDF5 file listing from the filesystem. In demo mode, the snapshot endpoints return mock data and don't read from the actual filesystem. Patching the global `_snapshots_dir` variable would require:

1. Modifying module-level initialization
2. Ensuring cleanup doesn't affect other tests
3. Handling race conditions in parallel test execution

**Alternative:** These tests are better suited for integration tests with a real backend.

### SK-004 & SK-005: TestClient CORS Middleware Bypass

**File:** `tests/integration/test_main_api_endpoints.py:276,282`
**Tests:** `test_cors_headers_present`, `test_cors_allows_all_origins`
**Reason:** FastAPI TestClient bypasses CORS middleware

The FastAPI TestClient makes requests directly to the ASGI application without going through HTTP middleware layers. CORS headers are added by the `CORSMiddleware` which only activates for actual HTTP requests with `Origin` headers.

**Reference:** <https://github.com/tiangolo/fastapi/discussions/7726>

**Alternative:** Use `httpx` with a running server for CORS testing (requires `@pytest.mark.requires_server`).

## Consequences

### Positive

- Clear documentation of why certain tests are skipped
- Prevents future developers from trying to "fix" valid skips
- Establishes a pattern for documenting architectural test limitations

### Negative

- Some functionality is not automatically tested
- Requires manual testing for CORS and HDF5 file operations

### Mitigation

- Manual testing procedures documented in `docs/testing/MANUAL_TEST_CHECKLIST.md`
- Integration tests with real backend (`@pytest.mark.requires_cascor`) cover HDF5 operations
- E2E tests with running server (`@pytest.mark.requires_server`) can test CORS

## Related Issues

- Epic 3.2: Address Unconditional Skips
- TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md

## Updates

| Date       | Change              |
| ---------- | ------------------- |
| 2026-02-04 | Initial ADR created |
