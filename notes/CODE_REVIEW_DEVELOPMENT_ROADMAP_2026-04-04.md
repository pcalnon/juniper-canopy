# Juniper Canopy -- Code Review Development Roadmap

**Date**: 2026-04-04
**Version**: 0.4.0
**Companion Documents**:

- [CODE_REVIEW_ANALYSIS_2026-04-04.md](CODE_REVIEW_ANALYSIS_2026-04-04.md)
- [CODE_REVIEW_PLAN_2026-04-04.md](CODE_REVIEW_PLAN_2026-04-04.md)

---

## Roadmap Overview

```text
Phase 0 ─── Pre-Release Security Blockers ────── [BLOCK: Release]
   │
Phase 1 ─── Release-Critical Quality Fixes ───── [BLOCK: Release]
   │
   ├── Phase 2 ── CI/CD Infrastructure ────────── [HIGH: Pre/Post-Release]
   │
   ├── Phase 3 ── Code Quality & Observability ── [MEDIUM: Post-Release]
   │
   └── Phase 4 ── Test Coverage Expansion ──────── [MEDIUM: Post-Release]

Phase 5 ─── Housekeeping & Low Priority ───────── [LOW: Ongoing, No Dependencies]
```

---

## Phase 0: Pre-Release Security Blockers

**Status**: Not Started
**Priority**: IMMEDIATE
**Branch**: `fix/pre-release-security-audit`
**Blocks**: Release, all subsequent phases

### Tasks

- [ ] **0.1.1** Fix path traversal in snapshot endpoints (`src/main.py`)
  - Add `_sanitize_snapshot_name()` regex validation
  - Add `.resolve()` path confinement check
  - Write targeted security test
- [ ] **0.1.2** Fix timing attack in API key validation (`src/security.py`)
  - Replace `in` operator with `hmac.compare_digest()`
- [ ] **0.1.3** Suppress internal details in exception handler (`src/main.py`)
  - Log full exception server-side, return generic message to client
- [ ] **0.1.4** Fix rate limiter memory leak (`src/security.py`)
  - Add `_evict_expired()` method with periodic cleanup
  - Add emergency size cap (10,000 entries)
- [ ] **0.2.1** Fix thread-unsafe CallbackContextAdapter (`src/frontend/callback_context.py`)
  - Replace instance attributes with `contextvars.ContextVar`
- [ ] **0.2.2** Fix threading.Event replacement race (`src/demo_mode.py`)
  - Use `_stop.clear()` instead of `_stop = Event()`

### Acceptance Criteria

- All 6 tasks completed with targeted tests
- Full test suite: 4,169+ passed, 0 failed
- Security-focused tests added for each vulnerability
- Pre-commit hooks pass

---

## Phase 1: Release-Critical Quality Fixes

**Status**: Not Started
**Priority**: HIGH
**Branch**: `fix/release-critical-quality`
**Depends On**: Phase 0

### Step 1.1: API and WebSocket Fixes (7 tasks)

- [ ] **1.1.1** Fix `/ws` exception handling loop (`src/main.py`)
- [ ] **1.1.2** Enforce `max_connections` in WebSocketManager (`src/communication/websocket_manager.py`)
- [ ] **1.1.3** Stop `broadcast()` mutating message dicts (`src/communication/websocket_manager.py`)
- [ ] **1.1.4** Remove duplicate `cn_patience` (`src/main.py`)
- [ ] **1.1.5** Define Pydantic model for `set_params` endpoint (`src/main.py`)
- [ ] **1.1.6** Handle malformed Content-Length (`src/middleware.py`)
- [ ] **1.1.7** Restrict CORS to used methods/headers (`src/main.py`)

### Step 1.2: Configuration Consistency (5 tasks)

- [ ] **1.2.1** Centralize version via `importlib.metadata` (`src/main.py`)
- [ ] **1.2.2** Update `app_config.yaml` version to 0.4.0
- [ ] **1.2.3** Update `pyproject.toml` header version comment
- [ ] **1.2.4** Use `get_settings()` in `get_rate_limiter()` (`src/security.py`)
- [ ] **1.2.5** Fix CORS YAML syntax (`conf/app_config.yaml`)

### Step 1.3: Frontend Critical Fixes (3 tasks)

- [ ] **1.3.1** Replace `_api_url()` with settings-based construction (`src/frontend/dashboard_manager.py`)
- [ ] **1.3.2** Fix static screenshot timestamp (`src/frontend/components/network_visualizer.py`)
- [ ] **1.3.3** Deduplicate accuracy plot phase band logic (`src/frontend/components/metrics_panel.py`)

### Acceptance Criteria

- All 15 tasks completed
- Full test suite: 4,169+ passed, 0 failed
- API documentation (OpenAPI) updated for `set_params` endpoint
- No version string mismatches across health/status endpoints

---

## Phase 2: CI/CD Infrastructure Reliability

**Status**: Not Started
**Priority**: HIGH
**Branch**: `fix/ci-cd-infrastructure`
**Depends On**: Phase 1 (for clean merge base)

### Step 2.1: CI Pipeline (5 tasks)

- [ ] **2.1.1** Fix lockfile extras mismatch (`.github/workflows/lockfile-update.yml`)
- [ ] **2.1.2** Add `contents: read` to publish permissions (`.github/workflows/publish.yml`)
- [ ] **2.1.3** Fix pip-audit to scan full dependencies (`.github/workflows/ci.yml`)
- [ ] **2.1.4** Define `dev` extra in pyproject.toml
- [ ] **2.1.5** Add Codecov upload step to CI

### Step 2.2: Security Scanning (3 tasks)

- [ ] **2.2.1** Consolidate bandit to single config file
- [ ] **2.2.2** Standardize bandit invocations in workflows
- [ ] **2.2.3** Fix mypy strict_optional conflict

### Step 2.3: Docker Configuration (4 tasks)

- [ ] **2.3.1** Create production config or document env var overrides
- [ ] **2.3.2** Pin all Docker dependencies via lockfile
- [ ] **2.3.3** Fix Docker service URL defaults
- [ ] **2.3.4** Change log file handler to append mode

### Acceptance Criteria

- Dependabot PRs pass CI (simulate)
- Bandit results identical from all invocation paths
- Docker build succeeds and health check passes
- Full test suite: 4,169+ passed, 0 failed

---

## Phase 3: Code Quality and Observability

**Status**: Not Started
**Priority**: MEDIUM
**Branch**: `chore/code-quality-improvements`
**Depends On**: Phase 1
**Can Parallel With**: Phase 2, Phase 4

### Step 3.1: Logging and Observability (6 tasks)

- [ ] **3.1.1** Fix ColoredFormatter LogRecord mutation
- [ ] **3.1.2** Cache logger wrapper instances
- [ ] **3.1.3** Make Sentry sample rate configurable
- [ ] **3.1.4** Normalize Prometheus endpoint labels
- [ ] **3.1.5** Use async probes for health checks
- [ ] **3.1.6** Set production-safe default log levels

### Step 3.2: Dead Code Removal (5 tasks)

- [ ] **3.2.1** Remove dead `_create_candidate_pool_display` from MetricsPanel
- [ ] **3.2.2** Remove orphaned candidate callbacks from MetricsPanel
- [ ] **3.2.3** Extract shared `create_empty_plot()` utility
- [ ] **3.2.4** Remove or deprecate legacy `TrainingMetricsComponent`
- [ ] **3.2.5** Remove commented imports

### Step 3.3: Frontend Patterns (5 tasks)

- [ ] **3.3.1** Extract hardcoded colors to `theme_constants.py`
- [ ] **3.3.2** Fix modulo toggle to use State
- [ ] **3.3.3** Fix broken documentation links in About panel
- [ ] **3.3.4** Remove blocking `time.sleep()` from parameter retry
- [ ] **3.3.5** Split overloaded NetworkVisualizer callback

### Step 3.4: Performance (2 tasks)

- [ ] **3.4.1** Reduce API timeout for fast-interval callbacks
- [ ] **3.4.2** Begin DashboardManager extraction (sidebar, controls, stores, theme)

### Acceptance Criteria

- No ANSI codes in file log output
- Prometheus cardinality stable under varied requests
- Theme changes require editing one file
- DashboardManager below 2,000 lines after extraction
- Full test suite: 4,169+ passed, 0 failed

---

## Phase 4: Test Coverage Expansion

**Status**: Not Started
**Priority**: MEDIUM
**Branch**: `test/coverage-expansion`
**Can Parallel With**: Phase 2, Phase 3

### Step 4.1: Coverage Gap Fills (4 tasks)

- [ ] **4.1.1** `tests/unit/test_discovery.py` -- service discovery probing
- [ ] **4.1.2** `tests/unit/test_observability.py` -- Prometheus/Sentry
- [ ] **4.1.3** `tests/unit/test_secrets_util.py` -- SOPS paths
- [ ] **4.1.4** `tests/unit/test_middleware_edge_cases.py` -- malformed headers

### Step 4.2: New Test Types (4 tasks)

- [ ] **4.2.1** `tests/security/test_auth_security.py` -- auth bypass, injection, CORS
- [ ] **4.2.2** `tests/performance/test_websocket_load.py` -- concurrent connections
- [ ] **4.2.3** `tests/unit/backend/test_circuit_breaker_resilience.py` -- failure scenarios
- [ ] **4.2.4** `tests/integration/test_api_contract_validation.py` -- schema enforcement

### Acceptance Criteria

- Coverage for `discovery.py`, `observability.py`, `secrets_util.py` > 80%
- Security test suite exercises all authentication paths
- Full test suite: 4,200+ passed, 0 failed

---

## Phase 5: Housekeeping and Low Priority

**Status**: Not Started
**Priority**: LOW
**Branch**: Various `chore/*` branches
**No Dependencies**: Can be done anytime

### Configuration (5 tasks)

- [ ] **5.1.1** Add deprecation warnings to remaining legacy env validators
- [ ] **5.1.2** Fix `_convert_type` boolean/integer precedence
- [ ] **5.1.3** Migrate `CASCOR_SNAPSHOT_DIR` to `JUNIPER_CANOPY_SNAPSHOT_DIR`
- [ ] **5.1.4** Add `py314` to Black target-version
- [ ] **5.1.5** Create CPU-only conda environment

### Logging (4 tasks)

- [ ] **5.2.1** Capture real call site in `_log_with_context`
- [ ] **5.2.2** Use timezone-aware timestamps
- [ ] **5.2.3** Replace print() with logger
- [ ] **5.2.4** Resolve FATAL_LEVEL conflict

### Minor Code Fixes (6 tasks)

- [ ] **5.3.1** Fix `config.key` AttributeError
- [ ] **5.3.2** Add message size check to training WebSocket
- [ ] **5.3.3** Narrow exception types in callback_context
- [ ] **5.3.4** Forward parameters in `_layout_type_sprint`
- [ ] **5.3.5** Verify `_format_hit_rate` percentage contract
- [ ] **5.3.6** Make header title color theme-aware

### CI/CD Housekeeping (4 tasks)

- [ ] **5.4.1** Consider curl-based Docker health check
- [ ] **5.4.2** Align shellcheck severity to ecosystem convention
- [ ] **5.4.3** Run `pre-commit autoupdate`
- [ ] **5.4.4** Document codecov build count assumption

---

## Phase 0 Addendum: Backend Concurrency (From Supplementary Review)

- [ ] **0.3.1** Add `threading.Lock` to `TrainingStateMachine` (HIGH-015, `src/backend/training_state_machine.py`)

## Phase 1 Addendum: Backend Fixes (From Supplementary Review)

- [ ] **1.4.1** Guard `get_dataset` against KeyError on partial data (MED-036, `src/backend/service_backend.py`)
- [ ] **1.4.2** Fix `prepare_dataset_for_visualization` None crash (MED-038, `src/backend/data_adapter.py`)
- [ ] **1.4.3** Add thread-safe locking to Cassandra singleton (MED-039, `src/backend/cassandra_client.py`)
- [ ] **1.4.4** Add thread-safe locking to Redis singleton (MED-041, `src/backend/redis_client.py`)
- [ ] **1.4.5** Fix Redis exception aliases to use sentinel class (MED-042, `src/backend/redis_client.py`)
- [ ] **1.4.6** Fix Redis `force_new=True` connection leak (MED-043, `src/backend/redis_client.py`)

## Phase 3 Addendum: Backend Quality (From Supplementary Review)

- [ ] **3.5.1** Cache `network` property or wrap in circuit breaker (MED-034, `src/backend/cascor_service_adapter.py`)
- [ ] **3.5.2** Narrow relay loop exception handling (MED-035, `src/backend/cascor_service_adapter.py`)
- [ ] **3.5.3** Lazy-import torch in data_adapter.py (MED-037, `src/backend/data_adapter.py`)
- [ ] **3.5.4** Expose public API on CascorServiceAdapter (MED-046, `src/backend/service_backend.py`)
- [ ] **3.5.5** Don't store Cassandra credentials as plain attributes (MED-040, `src/backend/cassandra_client.py`)

## Phase 4 Addendum: Test Quality Fixes (From Supplementary Review)

- [ ] **4.3.1** Remove `contextlib.suppress(Exception)` from test assertions (HIGH-016)
- [ ] **4.3.2** Add `pytest.fail()` guards to WebSocket schema tests (HIGH-017)
- [ ] **4.3.3** Remove `hasattr` guards from unit tests (HIGH-018)
- [ ] **4.3.4** Rewrite performance test without exception suppression (HIGH-019)
- [ ] **4.3.5** Add dedicated tests for `parameters_panel.py` (55.3% coverage gap)
- [ ] **4.3.6** Expand `candidate_metrics_panel.py` callback tests (65.6% coverage gap)

---

## Summary Statistics

| Phase | Tasks | Priority | Status |
|-------|-------|----------|--------|
| Phase 0 | 7 | IMMEDIATE | Not Started |
| Phase 1 | 21 | HIGH | Not Started |
| Phase 2 | 12 | HIGH | Not Started |
| Phase 3 | 23 | MEDIUM | Not Started |
| Phase 4 | 14 | MEDIUM | Not Started |
| Phase 5 | 19 | LOW | Not Started |
| **Total** | **96** | | |

### Issue Severity Distribution

| Severity | Issues | Resolution Phase(s) |
|----------|--------|---------------------|
| Critical | 3 | Phases 0, 2 |
| High | 19 | Phases 0, 1, 2, 3, 4 |
| Medium | 47 | Phases 1, 2, 3, 4, 5 |
| Low | 30+ | Phases 3, 5 |

### Files Most Affected

| File | Issues | Phases |
|------|--------|--------|
| `src/main.py` | 10 | 0, 1, 3, 5 |
| `src/frontend/dashboard_manager.py` | 6 | 1, 3 |
| `src/logger/logger.py` | 6 | 3, 5 |
| `src/security.py` | 3 | 0, 1 |
| `src/frontend/components/metrics_panel.py` | 4 | 1, 3 |
| `conf/app_config.yaml` | 3 | 1, 2 |
| `.github/workflows/ci.yml` | 3 | 2 |
| `src/communication/websocket_manager.py` | 2 | 1 |

---

*Document generated: 2026-04-04*
*This roadmap should be updated as tasks are completed and new issues are discovered.*
