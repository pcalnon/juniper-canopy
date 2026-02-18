# Pull Request: Integration & Enhancements — Backend, JuniperData, Test Suite, CI/CD, and Post-Release Roadmap

**Date:** 2026-02-18
**Version(s):** 0.24.0 → 0.31.0+ (Unreleased)
**Author:** Paul Calnon
**Status:** READY_FOR_MERGE

---

## Summary

This PR consolidates all integration and enhancement work on the `subproject.juniper_canopy.integration_and_enhancements` branch, spanning 80 commits over 5 weeks.
It delivers CasCor backend integration (async training, remote workers, in-process initialization), JuniperData service integration (REST client, Docker Compose), a comprehensive 4-phase test suite and CI/CD enhancement program, non-passing test remediation (67 tests fixed), CI/CD parity across all Juniper applications, and a post-release development roadmap consolidating 55 items from a full codebase audit.

**SemVer Impact:** MINOR
**Breaking Changes:** None

---

## Context / Motivation

Following the completion of the Phase 0-3 refactoring (v0.24.0), this branch addresses the next layer of integration and quality work:

- **CasCor Backend Integration**: The real backend mode needed in-process initialization, async training via `ThreadPoolExecutor`, remote worker management, and WebSocket control command handling
- **JuniperData Integration**: Spiral dataset generation needed to be delegated to the JuniperData microservice with graceful fallback to local generation
- **Test Suite Quality**: False-positive tests (`assert True` patterns), unconditional skips, exception suppression in tests, duplicate test classes, and 67 non-passing tests all required remediation
- **CI/CD Parity**: All three Juniper applications (JuniperCascor, JuniperData, JuniperCanopy) needed identical CI/CD settings
- **Post-Release Roadmap**: 45+ planning/audit notes files needed consolidation into a single prioritized roadmap with codebase validation

**Related Documentation:**

- [JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](../JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md) - Consolidated 55-item roadmap
- [CASCOR-AUDIT_CROSS-REFERENCES_2026-02-18.md](../CASCOR-AUDIT_CROSS-REFERENCES_2026-02-18.md) - Cross-references from CasCor audit
- [notes/history/INDEX.md](../history/INDEX.md) - Archive index for evaluated planning documents

---

## Priority & Work Status

| Priority | Work Item                                                  | Owner            | Status      |
| -------- | ---------------------------------------------------------- | ---------------- | ----------- |
| P0       | CasCor in-process backend initialization (RC-1/RC-2)       | Development Team | ✅ Complete |
| P0       | WebSocket control commands for real backend (RC-3)         | Development Team | ✅ Complete |
| P0       | Missing pytest-mock dependency                             | Development Team | ✅ Complete |
| P0       | Non-passing test remediation (67 tests)                    | Development Team | ✅ Complete |
| P1       | Async training boundary (P1-NEW-003)                       | Development Team | ✅ Complete |
| P1       | RemoteWorkerClient integration (P1-NEW-002)                | Development Team | ✅ Complete |
| P1       | JuniperData service integration                            | Development Team | ✅ Complete |
| P1       | JuniperData API contract fixes                             | Development Team | ✅ Complete |
| P1       | JUNIPER_DATA_URL validation in all modes (RC-5)            | Development Team | ✅ Complete |
| P1       | CI/CD parity across all Juniper applications               | Development Team | ✅ Complete |
| P2       | Test Suite & CI/CD Enhancement Phase 1 (false positives)   | Development Team | ✅ Complete |
| P2       | Test Suite & CI/CD Enhancement Phase 2 (conftest, linting) | Development Team | ✅ Complete |
| P2       | Test Suite & CI/CD Enhancement Phase 3 (weak tests, skips) | Development Team | ✅ Complete |
| P2       | Test Suite & CI/CD Enhancement Phase 4 (config, MyPy)      | Development Team | ✅ Complete |
| P2       | Post-release development roadmap audit                     | Development Team | ✅ Complete |
| P3       | Mode flag synchronization (CF-1)                           | Development Team | ✅ Complete |
| P3       | Startup script cleanup (RC-4)                              | Development Team | ✅ Complete |

### Priority Legend

- **P0:** Critical - Core bugs or blockers
- **P1:** High - High-impact features or fixes
- **P2:** Medium - Polish and medium-priority
- **P3:** Low - Advanced/infrastructure features

---

## Changes

### Added

- **CasCor Backend Integration** (`src/backend/cascor_integration.py`)
  - Async training support via `ThreadPoolExecutor` with `max_workers=1`
  - `fit_async()` method using `asyncio.run_in_executor()`
  - `start_training_background()` for fire-and-forget training
  - `is_training_in_progress()` and `request_training_stop()` methods
  - RemoteWorkerClient integration: `connect_remote_workers()`, `start_remote_workers()`, `stop_remote_workers()`, `disconnect_remote_workers()`, `get_remote_worker_status()`
  - Thread-safe metrics extraction with `self.metrics_lock`

- **CasCor Real Backend Mode** (`src/main.py`)
  - In-process backend initialization: network creation, monitoring hooks, dataset fetch from JuniperData
  - `/ws/control` handling for start/stop/reset commands with real backend
  - `POST /api/train/start`, `POST /api/train/stop`, `GET /api/train/status` endpoints
  - Remote worker endpoints: `GET /api/remote/status`, `POST /api/remote/connect`, `POST /api/remote/start_workers`, `POST /api/remote/stop_workers`, `POST /api/remote/disconnect`
  - State message on `/ws/training` connect using `training_state.get_state()` format
  - HDF5 snapshot filter excluding private attributes

- **JuniperData Integration**
  - New module: `src/juniper_data_client/` (client.py, exceptions.py, "\__init__\".py)
    - `JuniperDataClient.create_dataset()`, `download_artifact_npz()`, `get_preview()`
  - `src/demo_mode.py`: `_generate_spiral_dataset_from_juniper_data()` with fallback to local generation
  - `src/backend/cascor_integration.py`: `_generate_dataset_from_juniper_data()` with fallback
  - Feature flag: `JUNIPER_DATA_URL` enables JuniperData mode
  - Docker Compose service definition in `conf/docker-compose.yaml`

- **Canopy Constants Module** (`src/canopy_constants.py`)
  - Centralized constants management replacing `constants.py`

- **Integration Tests** (42+ new tests)
  - `test_cascor_real_backend_init.py` — 7 tests for in-process backend initialization
  - `test_cascor_ws_control.py` — 9 tests for WebSocket control commands
  - `test_cascor_lifecycle.py` — 8 tests for CascorIntegration lifecycle
  - `test_cascor_api_compatibility.py` — 21 tests for API contract verification
  - `test_juniper_data_integration.py` — 11 tests for JuniperData integration (CAN-INT-001 to CAN-INT-011)

- **Unit Tests** (20+ new tests)
  - `test_juniper_data_url_validation.py` — 5 tests for URL validation in both modes
  - `test_config_expansion.py` — Config expansion tests
  - `test_data_adapter_normalization.py` — 20 tests for metrics normalization

- **Regression Tests** (13+ new tests)
  - `test_mode_flag_consistency.py` — 13 tests for CASCOR_DEMO_MODE flag parsing

- **Documentation**
  - `notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md` — 55-item consolidated roadmap with codebase validation
  - `notes/CASCOR-AUDIT_CROSS-REFERENCES_2026-02-18.md` — Cross-references from CasCor audit
  - `notes/history/INDEX.md` — Archive index for 14 evaluated planning documents
  - `docs/testing/ADR_001_VALID_TEST_SKIPS.md` — ADR documenting legitimate test skip patterns
  - `docs/testing/TEST_DIRECTORY_STRUCTURE.md` — Test directory documentation
  - `.bandit.yml` — Bandit security scan configuration
  - `util/verification/` — 5 manual verification scripts relocated from test directory

### Changed

- **Test Suite & CI/CD Enhancement Phase 1** (v0.28.0)
  - Eliminated 9 `assert True` false-positive patterns across 6 test files
  - Moved 5 non-test files from test directory to `util/verification/`
  - Fixed Bandit and pip-audit to fail on issues (removed `|| true` suppression)

- **Test Suite & CI/CD Enhancement Phase 2** (v0.29.0)
  - Deleted duplicate `src/tests/fixtures/conftest.py` (224 lines)
  - Fixed ConfigManager `__init__` type annotation (`Optional[str]` → `Optional[Union[str, Path]]`)
  - Added separate flake8 hook for tests with relaxed settings

- **Test Suite & CI/CD Enhancement Phase 3** (v0.30.0)
  - Fixed 5 tests using try/except/success antipattern (converted to direct assertions)
  - Converted 4 unconditional `@pytest.mark.skip` to conditional markers
  - Reduced `in [200, 503]`/`in [200, 400, 500]` assertion patterns from 21 to 5
  - Removed 111 lines of duplicate test classes from `test_main_coverage_95.py`
  - Re-enabled Flake8 checks: B905, F401, B008 for source code
  - Added `strict=True` to `zip()` calls in `cascor_integration.py` and `hdf5_snapshots_panel.py`

- **Test Suite & CI/CD Enhancement Phase 4** (v0.31.0)
  - Standardized `.coveragerc` `fail_under` to 80%
  - Re-enabled 9 MyPy error codes with 0 violations
  - Reviewed and documented all `contextlib.suppress` patterns
  - Added docs/ to markdown linting

- **CI/CD Parity** (v0.27.0)
  - Line length: 512 for black, isort, flake8 across all Juniper applications
  - Coverage threshold: 80% fail-under, 90% target
  - Added build job, yamllint hook, enabled mypy in CI
  - Standardized artifact paths: `reports/junit/`, `reports/htmlcov/`, `reports/coverage.xml`

- **Backend Configuration**
  - `conf/app_config.yaml`: Backend path now uses `${CASCOR_BACKEND_PATH}` with default
  - Startup script (`util/juniper_canopy.bash`): Removed `nohup` background process, exports `CASCOR_DEMO_MODE` and `CASCOR_BACKEND_PATH`

- **Metrics Normalization** (`src/backend/data_adapter.py`)
  - `normalize_metrics()` and `denormalize_metrics()` for Cascor↔Canopy key mapping (`value_loss`↔`val_loss`, `value_accuracy`↔`val_accuracy`)

- **Post-Release Roadmap Consolidation**
  - Archived 14 evaluated planning documents to `notes/history/`
  - Consolidated into single `JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md`
  - Cross-project items added to JuniperCascor and JuniperData roadmaps

### Fixed

- **RC-1/RC-2**: Real backend mode now creates network, installs hooks, starts monitoring, fetches dataset during lifespan startup
- **RC-3**: `/ws/control` handles start/stop/reset for CasCor backend (pause/resume return "not supported")
- **RC-4**: Removed `nohup` background CasCor process from startup script
- **RC-5**: JUNIPER_DATA_URL validation moved before demo/real mode branch
- **CF-1**: Startup script exports `CASCOR_DEMO_MODE` for consistent mode detection
- **CF-3**: Startup script exports `CASCOR_BACKEND_PATH` for CascorIntegration
- **CANOPY-P1-003**: Thread-safe metrics extraction with `threading.Lock()`
- **CANOPY-P2-001**: Replaced deprecated `asyncio.iscoroutinefunction()` with `inspect.iscoroutinefunction()`
- **JuniperData API contract**: Fixed param keys (`n_points` → `n_points_per_spiral`), response keys (`id` → `dataset_id`), NPZ keys (`inputs/targets` → `X_full/y_full`)
- **Logger VERBOSE level**: Changed to `self.VERBOSE_LEVEL` instead of non-existent `logging.VERBOSE`
- **LoggingConfig empty YAML**: Added null check after `yaml.safe_load()`
- **HDF5 snapshot private attribute leakage**: Added `not key.startswith("_")` filter
- **WebSocket state tests**: Added state message on connect, rewrote deterministic connect sequence
- **WebSocket ping-pong tests**: Updated to drain 3rd connect message
- **DemoMode singleton isolation**: Extended `reset_singletons` fixture to reset `_demo_instance`
- **WebSocket control command race condition**: Drain interleaved broadcast messages before asserting
- **67 non-passing tests**: 54 ERROR (missing pytest-mock), 10 FAILED (race conditions, wrong assertions), 3 XFAIL (now fixed)

### Removed

- `src/tests/fixtures/conftest.py` — Duplicate conftest eliminated (Phase 2)
- 4 duplicate test classes from `test_main_coverage_95.py` (111 lines)
- 3 `@pytest.mark.xfail` markers from `test_logger_coverage_95.py` (bugs fixed)
- 1 `@pytest.mark.skip` from `test_logger_coverage.py` (bug fixed)

### Security

- Fixed Bandit security scan to properly fail on issues (was suppressed by `|| true`)
- Fixed pip-audit to fail on vulnerabilities (was warning-only)
- Added `.bandit.yml` with excluded directories and documented check skips
- Re-enabled Flake8 B905 (zip without strict=), F401 (unused imports), B008 (default arguments) for source code

---

## Impact & SemVer

- **SemVer impact:** MINOR
- **User-visible behavior change:** YES — Real backend mode now functional with in-process CasCor; JuniperData integration available via `JUNIPER_DATA_URL`
- **Breaking changes:** NO
- **Performance impact:** IMPROVED — Async training prevents event loop blocking; thread-safe metrics extraction prevents race conditions
- **Security/privacy impact:** LOW — CI security scans now enforced; Flake8 checks re-enabled
- **Guarded by feature flag:** YES — `JUNIPER_DATA_URL` (JuniperData integration), `CASCOR_DEMO_MODE` (demo vs real backend)

---

## Testing & Results

### Test Summary

| Test Type   | Passed | Failed | Skipped | Notes                                           |
| ----------- | ------ | ------ | ------- | ----------------------------------------------- |
| Unit        | ~2400  | 0      | 0       | All unit tests passing                          |
| Integration | ~800   | 0      | 37      | Skipped require CASCOR_BACKEND, server, display |
| Regression  | 30+    | 0      | 0       | Mode flag, startup, candidate visibility        |
| Performance | 4+     | 0      | 0       | Button responsiveness tests                     |

**Total Tests:** 3,215+ passed, 0 failed, 0 errors, 37 skipped (all legitimate)

### Coverage

| Component             | Before (v0.24.0) | After | Target | Status           |
| --------------------- | ---------------- | ----- | ------ | ---------------- |
| data_adapter.py       | 100%             | 100%  | 95%    | ✅ Exceeded      |
| cascor_integration.py | 100%             | 100%  | 95%    | ✅ Exceeded      |
| websocket_manager.py  | 94%              | 100%  | 95%    | ✅ Exceeded      |
| dashboard_manager.py  | 93%              | 95%   | 95%    | ✅ Met           |
| redis_panel.py        | 49%              | 100%  | 95%    | ✅ Exceeded      |
| redis_client.py       | 76%              | 97%   | 95%    | ✅ Exceeded      |
| cassandra_client.py   | 75%              | 97%   | 95%    | ✅ Exceeded      |
| statistics.py         | 91%              | 100%  | 95%    | ✅ Exceeded      |
| main.py               | 79%              | 84%   | 95%    | ⚠️ Near target   |

### Environments Tested

- Demo mode (local): ✅ All features functional
- JuniperPython conda environment: ✅ All tests pass
- Python 3.14: ✅ Compatible

---

## Verification Checklist

- [x] Main user flow(s) verified: Demo mode training cycle, WebSocket state delivery
- [x] Edge cases checked: Metrics normalization, thread safety, singleton isolation, JuniperData fallback
- [x] No regression in related areas: All Phase 0-3 features intact
- [x] Demo mode works with all new features
- [x] Feature defaults correct and documented
- [x] Logging/metrics updated if needed
- [x] Documentation updated: CHANGELOG.md, AGENTS.md, roadmap, cross-references
- [x] Pre-commit hooks pass: Black, isort, Flake8, MyPy, Bandit, markdownlint, yamllint

---

## API Changes

### New Endpoints

| Method | Endpoint                  | Description                                         | Breaking? |
| ------ | ------------------------- | --------------------------------------------------- | --------- |
| POST   | /api/train/start          | Start training (uses `start_training_background()`) | No        |
| POST   | /api/train/stop           | Stop training (supports cascor_integration)         | No        |
| GET    | /api/train/status         | Get training status                                 | No        |
| GET    | /api/remote/status        | Check remote worker status                          | No        |
| POST   | /api/remote/connect       | Connect to remote worker manager                    | No        |
| POST   | /api/remote/start_workers | Start remote workers                                | No        |
| POST   | /api/remote/stop_workers  | Stop remote workers                                 | No        |
| POST   | /api/remote/disconnect    | Disconnect from remote manager                      | No        |

### New Methods

| Module                | Method                      | Description                        |
| --------------------- | --------------------------- | ---------------------------------- |
| cascor_integration.py | fit_async()                 | Async training via run_in_executor |
| cascor_integration.py | start_training_background() | Fire-and-forget training           |
| cascor_integration.py | is_training_in_progress()   | Check training status              |
| cascor_integration.py | request_training_stop()     | Best-effort stop request           |
| cascor_integration.py | connect_remote_workers()    | Connect to remote manager          |
| cascor_integration.py | start_remote_workers()      | Start N workers                    |
| cascor_integration.py | stop_remote_workers()       | Stop workers with timeout          |
| cascor_integration.py | disconnect_remote_workers() | Disconnect from manager            |
| cascor_integration.py | get_remote_worker_status()  | Get worker status dict             |
| data_adapter.py       | normalize_metrics()         | Cascor → Canopy key mapping        |
| data_adapter.py       | denormalize_metrics()       | Canopy → Cascor key mapping        |
| JuniperDataClient     | create_dataset()            | Create/generate dataset            |
| JuniperDataClient     | download_artifact_npz()     | Download NPZ artifact              |
| JuniperDataClient     | get_preview()               | Get dataset preview                |

### Response Codes

All new endpoints follow existing conventions:

- `200` – Success
- `400` – Invalid parameters
- `500` – Internal error
- `503` – Backend unavailable (demo mode)

---

## Files Changed

**182 files changed** — 28,855 insertions(+), 6,093 deletions(-) (net from main)

### New Components

- `src/juniper_data_client/client.py` – REST client for JuniperData service
- `src/juniper_data_client/exceptions.py` – Custom exceptions for JuniperData client
- `src/juniper_data_client/__init__.py` – Package exports
- `src/canopy_constants.py` – Centralized constants module
- `.bandit.yml` – Bandit security scan configuration
- `src/.markdownlint.yaml` – Markdownlint configuration
- `.serena/project.yml` – Serena MCP project configuration
- `notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md` – 55-item consolidated roadmap
- `notes/CASCOR-AUDIT_CROSS-REFERENCES_2026-02-18.md` – CasCor audit cross-references
- `notes/history/INDEX.md` – Archive index for 14 evaluated planning documents
- `docs/testing/ADR_001_VALID_TEST_SKIPS.md` – ADR for legitimate test skips
- `docs/testing/TEST_DIRECTORY_STRUCTURE.md` – Test directory documentation
- `util/verification/` – 5 verification scripts relocated from test directory

### Modified Components

**Backend:**

- `src/backend/cascor_integration.py` – Async training, remote workers, thread-safe metrics, JuniperData integration
- `src/backend/data_adapter.py` – Metrics normalization methods
- `src/backend/redis_client.py` – Code quality improvements
- `src/backend/cassandra_client.py` – Code quality improvements
- `src/backend/training_monitor.py` – Readability improvements
- `src/main.py` – Real backend init, new endpoints, WebSocket state on connect, snapshot filter

**Frontend:**

- `src/frontend/dashboard_manager.py` – Handler improvements
- `src/frontend/components/hdf5_snapshots_panel.py` – zip() strict=True
- `src/frontend/components/cassandra_panel.py` – Removed unused import
- `src/frontend/components/metrics_panel.py` – Code quality
- `src/frontend/components/network_visualizer.py` – Code quality
- `src/frontend/components/training_metrics.py` – Code quality

**Core:**

- `src/demo_mode.py` – JuniperData integration, API contract fixes
- `src/config_manager.py` – Type annotation fix, suppress documentation
- `src/communication/websocket_manager.py` – Suppress documentation, coverage improvements
- `src/logger/logger.py` – VERBOSE level fix, empty YAML fix

**Configuration:**

- `conf/app_config.yaml` – Backend path via env var
- `conf/docker-compose.yaml` – JuniperData service
- `conf/conda_environment.yaml` – Updated for CI/CD
- `.pre-commit-config.yaml` – CI/CD parity, test linting, yamllint, MyPy
- `.github/workflows/ci.yml` – Security scan enforcement, build job, coverage threshold
- `pyproject.toml` – Line length, coverage, dependencies

**Tests (68 files):**

- 42+ new integration tests for CasCor backend and JuniperData
- 20+ new unit tests for normalization, config, URL validation
- 13+ regression tests for mode flag consistency
- False-positive elimination, race condition fixes, singleton isolation
- Duplicate class removal, skip/xfail cleanup

**Documentation (30 files):**

- `CHANGELOG.md` – v0.24.1 through v0.31.0+ entries
- `AGENTS.md` / `CLAUDE.md` – Updated with recent changes
- `README.md` – Updated features
- 30 docs files updated across testing, CI/CD, cascor, demo subdirectories

**Notes (19 files):**

- Post-release roadmap, cross-references, archive index
- 14 planning documents moved to `notes/history/`
- Release notes for v0.25.0-alpha

---

## Risks & Rollback Plan

- **Key risks:**
  - Real backend mode has not been tested with a live CasCor instance (in-process init tested via mocks)
  - JuniperData integration depends on service availability (graceful fallback to local generation mitigates)
- **Monitoring / alerts to watch:** WebSocket message delivery under load, training thread memory usage
- **Rollback plan:** Set `CASCOR_DEMO_MODE=1` to bypass real backend; unset `JUNIPER_DATA_URL` to disable JuniperData integration

---

## Related Issues / Tickets

- Issues: RC-1 through RC-5, CF-1, CF-3, CANOPY-P1-003, CANOPY-P2-001
- Design / Spec: [PRE-DEPLOYMENT_ROADMAP-2.md](../history/PRE-DEPLOYMENT_ROADMAP.md), [INTEGRATION_ROADMAP.md](../history/INTEGRATION_ROADMAP.md)
- Related PRs: [PR_DESCRIPTION_RELEASE_v0.25.0_2026-01-25.md](PR_DESCRIPTION_RELEASE_v0.25.0_2026-01-25.md), [PR_DESCRIPTION_POST_REFACTOR_v0.24.0_2026-01-11.md](PR_DESCRIPTION_POST_REFACTOR_v0.24.0_2026-01-11.md)
- Phase Documentation: [TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md](../history/TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md)

---

## What's Next

### Remaining Items

| Feature                                           | Status                                | Priority |
| ------------------------------------------------- | ------------------------------------- | -------- |
| Decision boundary for real backend (CAN-CRIT-001) | Blocked by CasCor Prediction Grid API | P0       |
| save_snapshot() / load_snapshot() (CAN-CRIT-002)  | Blocked by CasCor Serialization API   | P0       |
| Real backend integration tests with live CasCor   | Not started                           | P1       |
| Coverage improvement to 90% (main.py target)      | In progress                           | P2       |
| Dashboard enhancements (CAN-001 through CAN-021)  | Roadmapped                            | P3       |
| Full IPC architecture (INT-P1-004)                | Deferred                              | P4       |

See [JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](../JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md) for the complete 55-item prioritized roadmap.

---

## Notes for Release

**Release: Juniper Canopy v0.31.0+ — Integration & Enhancements:**

Key highlights:

- CasCor real backend mode now functional with in-process initialization, async training, and remote worker management
- JuniperData microservice integration for spiral dataset generation (feature-flagged via `JUNIPER_DATA_URL`)
- Complete 4-phase test suite and CI/CD enhancement program (false positives eliminated, security scans enforced, CI/CD parity achieved)
- 67 non-passing tests fixed — final result: 3,215 passed, 0 failed, 37 skipped
- 8 new API endpoints for training control and remote worker management
- Comprehensive post-release development roadmap with 55 prioritized items from full codebase audit
- 182 files changed, 80 commits, 28,855 lines added

---

## Review Notes

1. **Real Backend Mode**: The in-process CasCor initialization in `main.py` lifespan is the most significant architectural change. CasCor runs inside the Canopy process, not as a separate OS process. The startup script no longer uses `nohup`.

2. **JuniperData Client**: The `juniper_data_client` module is a standalone REST client. API contract was verified against JuniperData v0.7.0+ and fixed in v0.26.1 (param keys, response keys, NPZ keys).

3. **Test Suite Enhancement**: The 4-phase program systematically addressed test quality issues. Phase 3 is the most invasive (weak test fixes, Flake8 re-enablement). All changes maintain backward compatibility.

4. **67 Non-Passing Tests**: Root causes were: missing pytest-mock (54 errors), race conditions in WebSocket tests (3 failures), wrong assertion codes in demo mode tests (4 failures), logger bugs (3 xfail), singleton isolation (2 failures), unconditional skips (1).

5. **Post-Release Roadmap**: The 55-item roadmap was produced by auditing 45+ notes files with rigorous codebase validation. 14 source documents were archived to `notes/history/`. Cross-project items were added to JuniperCascor and JuniperData roadmaps.

6. **CI/CD Parity**: All three Juniper applications now use identical settings (line length 512, coverage 80%, Python 3.11-3.14 matrix). This enables consistent quality gates across the ecosystem.
