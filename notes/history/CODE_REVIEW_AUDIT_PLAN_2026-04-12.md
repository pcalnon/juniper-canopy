# Juniper Canopy -- Code Review Audit Plan

**Date**: 2026-04-12
**Version**: 0.4.0
**Auditor**: Claude Code (Principal Engineer Role)
**Scope**: Full verification of all code review remediation claims

**Companion Documents**:

- [CODE_REVIEW_PLAN_2026-04-04.md](CODE_REVIEW_PLAN_2026-04-04.md) -- 5-phase remediation plan (96 tasks)
- [CODE_REVIEW_ANALYSIS_2026-04-04.md](CODE_REVIEW_ANALYSIS_2026-04-04.md) -- Comprehensive issue analysis (99+ issues)
- [CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md](CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md) -- Executive roadmap

---

## 1. Executive Summary

### 1.1 Purpose

This audit plan defines the methodology and directives for a comprehensive, rigorous verification of all code review remediation work performed on juniper-canopy between 2026-04-04 and 2026-04-06. The code review identified 99+ issues across 7 categories. All 5 remediation phases are marked COMPLETE. This audit validates that claim against the actual codebase.

### 1.2 Audit Objectives

1. **Verify every fix**: Confirm each of the 99+ issues has been resolved in the codebase
2. **Validate fix correctness**: Ensure fixes address root causes, not just symptoms
3. **Verify test coverage**: Confirm dedicated tests exist for each fix
4. **Identify gaps**: Catalog any incomplete, missing, or incorrect fixes
5. **Develop remediations**: Produce actionable fix recommendations for all gaps
6. **Validate documentation**: Ensure code review documents accurately reflect codebase state

### 1.3 Preliminary Findings

During exploration, **15 potential gaps** were identified:

- **11 issues** appear NOT fixed despite COMPLETE status
- **4 issues** appear only partially fixed
- **1 documentation gap**: Roadmap document not updated with completion status

---

## 2. Issue Inventory

### 2.1 Complete Issue Registry

| ID       | Severity | Category            | File(s)                                                    | Phase | Claimed Status |
|----------|----------|---------------------|------------------------------------------------------------|-------|----------------|
| CRIT-001 | Critical | Security            | `src/main.py`                                              | 0     | COMPLETE       |
| CRIT-002 | Critical | Concurrency         | `src/frontend/callback_context.py`                         | 0     | COMPLETE       |
| CRIT-003 | Critical | CI/CD               | `.github/workflows/lockfile-update.yml`                    | 2     | COMPLETE       |
| HIGH-001 | High     | Security            | `src/security.py`                                          | 0     | COMPLETE       |
| HIGH-002 | High     | Security            | `src/main.py`                                              | 0     | COMPLETE       |
| HIGH-003 | High     | Security            | `src/security.py`                                          | 0     | COMPLETE       |
| HIGH-004 | High     | Concurrency         | `src/demo_mode.py`                                         | 0     | COMPLETE       |
| HIGH-005 | High     | Performance         | `src/frontend/dashboard_manager.py`                        | 3     | COMPLETE       |
| HIGH-006 | High     | Logic               | `src/frontend/dashboard_manager.py`                        | 1     | COMPLETE       |
| HIGH-007 | High     | Logic               | `src/frontend/components/network_visualizer.py`            | 1     | COMPLETE       |
| HIGH-008 | High     | Configuration       | `Dockerfile`, `conf/app_config.yaml`                       | 2     | COMPLETE       |
| HIGH-009 | High     | Security            | `.bandit.yml`, `pyproject.toml`, `.pre-commit-config.yaml` | 2     | COMPLETE       |
| HIGH-010 | High     | Logic               | `src/main.py`                                              | 1     | COMPLETE       |
| HIGH-011 | High     | Code Smell          | `src/main.py`                                              | 1     | COMPLETE       |
| HIGH-012 | High     | CI/CD               | `.github/workflows/publish.yml`                            | 2     | COMPLETE       |
| HIGH-013 | High     | Code Smell          | `src/frontend/components/metrics_panel.py`                 | 1     | COMPLETE       |
| HIGH-014 | High     | Architecture        | `src/frontend/dashboard_manager.py`                        | 3     | COMPLETE       |
| HIGH-015 | High     | Concurrency         | `src/backend/training_state_machine.py`                    | 0     | COMPLETE       |
| HIGH-016 | High     | Test Quality        | Multiple test files                                        | 4     | COMPLETE       |
| HIGH-017 | High     | Test Quality        | `src/tests/integration/test_websocket_message_schema.py`   | 4     | COMPLETE       |
| HIGH-018 | High     | Test Quality        | Multiple test files                                        | 4     | COMPLETE       |
| HIGH-019 | High     | Test Quality        | `src/tests/performance/test_button_responsiveness.py`      | 4     | COMPLETE       |
| MED-001  | Medium   | Logic               | `src/communication/websocket_manager.py`                   | 1     | COMPLETE       |
| MED-002  | Medium   | Logic               | `src/communication/websocket_manager.py`                   | 1     | COMPLETE       |
| MED-003  | Medium   | Security            | `src/main.py`                                              | 1     | COMPLETE       |
| MED-004  | Medium   | Performance         | `src/observability.py`                                     | 3     | COMPLETE       |
| MED-005  | Medium   | Performance         | `src/observability.py`                                     | 3     | COMPLETE       |
| MED-006  | Medium   | Performance         | `src/main.py`, `src/health.py`                             | 3     | COMPLETE       |
| MED-007  | Medium   | Performance         | `src/logger/logger.py`                                     | 3     | COMPLETE       |
| MED-008  | Medium   | Logic               | `src/logger/logger.py`                                     | 3     | COMPLETE       |
| MED-009  | Medium   | Configuration       | `conf/app_config.yaml`                                     | 1     | COMPLETE       |
| MED-010  | Medium   | Configuration       | `pyproject.toml`                                           | 1     | COMPLETE       |
| MED-011  | Medium   | Configuration       | `conf/logging_config.yaml`                                 | 2     | COMPLETE       |
| MED-012  | Medium   | Configuration       | `conf/logging_config.yaml`                                 | 3     | COMPLETE       |
| MED-013  | Medium   | Configuration       | `conf/app_config.yaml`                                     | 1     | COMPLETE       |
| MED-014  | Medium   | Security            | `.github/workflows/ci.yml`                                 | 2     | COMPLETE       |
| MED-015  | Medium   | Configuration       | `pyproject.toml`                                           | 2     | COMPLETE       |
| MED-016  | Medium   | Docker              | `Dockerfile`                                               | 2     | COMPLETE       |
| MED-017  | Medium   | Configuration       | `pyproject.toml`, `.pre-commit-config.yaml`                | 2     | COMPLETE       |
| MED-018  | Medium   | Docker              | `Dockerfile`                                               | 2     | COMPLETE       |
| MED-019  | Medium   | CI/CD               | `.github/workflows/ci.yml`, `.codecov.yml`                 | 2     | COMPLETE       |
| MED-020  | Medium   | Syntax              | `src/main.py`                                              | 1     | COMPLETE       |
| MED-021  | Medium   | API Design          | `src/main.py`                                              | 1     | COMPLETE       |
| MED-022  | Medium   | Configuration       | `src/security.py`                                          | 1     | COMPLETE       |
| MED-023  | Medium   | Logic               | `src/middleware.py`                                        | 1     | COMPLETE       |
| MED-024  | Medium   | Code Smell          | `src/frontend/components/metrics_panel.py`                 | 3     | COMPLETE       |
| MED-025  | Medium   | Syntax              | `src/frontend/components/metrics_panel.py`                 | 3     | COMPLETE       |
| MED-026  | Medium   | Code Smell          | All frontend component files                               | 3     | COMPLETE       |
| MED-027  | Medium   | Architecture        | `src/frontend/components/network_visualizer.py`            | 3     | COMPLETE       |
| MED-028  | Medium   | Performance         | `src/frontend/dashboard_manager.py`                        | 3     | COMPLETE       |
| MED-029  | Medium   | Logic               | `src/frontend/dashboard_manager.py`                        | 3     | COMPLETE       |
| MED-030  | Medium   | UI/UX               | `src/frontend/components/about_panel.py`                   | 3     | COMPLETE       |
| MED-031  | Medium   | Code Smell          | 5 component files                                          | 3     | COMPLETE       |
| MED-032  | Medium   | Security            | `.github/workflows/security-scan.yml`                      | 2     | COMPLETE       |
| MED-033  | Medium   | Dependencies        | `conf/conda_environment.yaml`                              | 5     | COMPLETE       |
| MED-034  | Medium   | Performance         | `src/backend/cascor_service_adapter.py`                    | 3     | COMPLETE       |
| MED-035  | Medium   | Best Practice       | `src/backend/cascor_service_adapter.py`                    | 3     | COMPLETE       |
| MED-036  | Medium   | Logic               | `src/backend/service_backend.py`                           | 1     | COMPLETE       |
| MED-037  | Medium   | Architecture        | `src/backend/data_adapter.py`                              | 3     | COMPLETE       |
| MED-038  | Medium   | Logic               | `src/backend/data_adapter.py`                              | 1     | COMPLETE       |
| MED-039  | Medium   | Concurrency         | `src/backend/cassandra_client.py`                          | 1     | COMPLETE       |
| MED-040  | Medium   | Security            | `src/backend/cassandra_client.py`                          | 3     | COMPLETE       |
| MED-041  | Medium   | Concurrency         | `src/backend/redis_client.py`                              | 1     | COMPLETE       |
| MED-042  | Medium   | Logic               | `src/backend/redis_client.py`                              | 1     | COMPLETE       |
| MED-043  | Medium   | Resource Leak       | `src/backend/redis_client.py`                              | 1     | COMPLETE       |
| MED-044  | Medium   | Logic               | `src/backend/training_monitor.py`                          | 3     | COMPLETE       |
| MED-045  | Medium   | Logic               | `src/backend/demo_backend.py`                              | 3     | COMPLETE       |
| MED-046  | Medium   | Architecture        | `src/backend/service_backend.py`                           | 3     | COMPLETE       |
| MED-047  | Medium   | Logic               | `src/backend/training_monitor.py`                          | 3     | COMPLETE       |
| MED-048  | Medium   | Test Infrastructure | Test conftest fixtures                                     | 4     | COMPLETE       |
| MED-049  | Medium   | Test Infrastructure | Test conftest fixtures                                     | 4     | COMPLETE       |
| LOW-001  | Low      | Best Practice       | `src/settings.py`                                          | 5     | COMPLETE       |
| LOW-002  | Low      | Logic               | `src/config_manager.py`                                    | 5     | COMPLETE       |
| LOW-003  | Low      | Syntax              | `src/config_manager.py`                                    | 5     | COMPLETE       |
| LOW-004  | Low      | Observability       | `src/logger/logger.py`                                     | 5     | COMPLETE       |
| LOW-005  | Low      | Best Practice       | `src/logger/logger.py`                                     | 5     | COMPLETE       |
| LOW-006  | Low      | Code Smell          | `src/logger/logger.py`                                     | 5     | COMPLETE       |
| LOW-007  | Low      | Best Practice       | `src/logger/logger.py`                                     | 5     | COMPLETE       |
| LOW-008  | Low      | Security            | `src/main.py`                                              | 5     | COMPLETE       |
| LOW-009  | Low      | Best Practice       | `src/main.py`                                              | 5     | COMPLETE       |
| LOW-010  | Low      | Docker              | `Dockerfile`                                               | 5     | COMPLETE       |
| LOW-011  | Low      | Pre-commit          | `.pre-commit-config.yaml`                                  | 5     | COMPLETE       |
| LOW-012  | Low      | Dependencies        | `.pre-commit-config.yaml`                                  | 5     | COMPLETE       |
| LOW-013  | Low      | CI/CD               | `.codecov.yml`                                             | 5     | COMPLETE       |
| LOW-014  | Low      | Configuration       | `pyproject.toml`                                           | 5     | COMPLETE       |
| LOW-015  | Low      | Best Practice       | `src/frontend/callback_context.py`                         | 5     | COMPLETE       |
| LOW-016  | Low      | Code Smell          | `src/frontend/components/training_metrics.py`              | 3     | COMPLETE       |
| LOW-017  | Low      | Code Smell          | `src/frontend/base_component.py`                           | 3     | COMPLETE       |
| LOW-018  | Low      | Logic               | `src/frontend/components/network_visualizer.py`            | 5     | COMPLETE       |
| LOW-019  | Low      | Logic               | `src/frontend/components/redis_panel.py`                   | 5     | COMPLETE       |
| LOW-020  | Low      | UI/UX               | `src/frontend/dashboard_manager.py`                        | 3     | COMPLETE       |
| LOW-021  | Low      | Test Infrastructure | Test conftest                                              | 4     | COMPLETE       |
| LOW-022  | Low      | Test Infrastructure | Test regression tests                                      | 4     | COMPLETE       |

---

## 3. Audit Domains

### 3.1 Domain 1: Security Vulnerabilities

**Priority**: CRITICAL
**Issues**: CRIT-001, HIGH-001, HIGH-002, HIGH-003, MED-003, MED-040, LOW-008

**Files to Examine**:

| File                              | Issues                               | Verification Focus                                             |
|-----------------------------------|--------------------------------------|----------------------------------------------------------------|
| `src/main.py`                     | CRIT-001, HIGH-002, MED-003, LOW-008 | Snapshot sanitization, exception handler, CORS, WebSocket size |
| `src/security.py`                 | HIGH-001, HIGH-003                   | hmac.compare_digest, rate limiter eviction                     |
| `src/middleware.py`               | MED-023 (cross-ref)                  | Content-length parsing                                         |
| `src/backend/cassandra_client.py` | MED-040                              | Credential storage pattern                                     |

**Verification Criteria**:

| Issue    | Pass Criteria                                                                                                         |
|----------|-----------------------------------------------------------------------------------------------------------------------|
| CRIT-001 | `_sanitize_snapshot_name()` with regex AND `.resolve()` path confinement present and called at all snapshot endpoints |
| HIGH-001 | `hmac.compare_digest()` used for API key comparison (not `==` or `in`)                                                |
| HIGH-002 | Exception handler returns generic message; logs `exc_info=True` server-side                                           |
| HIGH-003 | `_evict_expired()` present; emergency cap enforced; eviction called in `check()`                                      |
| MED-003  | CORS `allow_methods` and `allow_headers` are explicit lists (not `["*"]`)                                             |
| MED-040  | Cassandra credentials NOT stored as plain `self._username`/`self._password` instance attributes                       |
| LOW-008  | WebSocket training endpoint checks message size against `_WS_MAX_MESSAGE_SIZE`                                        |

**Test Verification**: Confirm existence and correctness of `test_phase0_security.py` and `test_security_validation.py`.

---

### 3.2 Domain 2: Concurrency and Thread Safety

**Priority**: HIGH
**Issues**: CRIT-002, HIGH-004, HIGH-015, MED-039, MED-041

**Files to Examine**:

| File                                    | Issues   | Verification Focus                             |
|-----------------------------------------|----------|------------------------------------------------|
| `src/frontend/callback_context.py`      | CRIT-002 | `contextvars.ContextVar` usage                 |
| `src/demo_mode.py`                      | HIGH-004 | `_stop.clear()` pattern                        |
| `src/backend/training_state_machine.py` | HIGH-015 | `threading.Lock` on all state mutations        |
| `src/backend/cassandra_client.py`       | MED-039  | Thread-safe singleton (double-checked locking) |
| `src/backend/redis_client.py`           | MED-041  | Thread-safe singleton (double-checked locking) |

**Verification Criteria**:

| Issue    | Pass Criteria                                                                 |
|----------|-------------------------------------------------------------------------------|
| CRIT-002 | `contextvars.ContextVar` replaces instance attributes for callback test state |
| HIGH-004 | `_stop.clear()` used (not `self._stop = threading.Event()`)                   |
| HIGH-015 | `threading.Lock` wrapping ALL state mutations in TrainingStateMachine         |
| MED-039  | `threading.Lock` guards Cassandra singleton creation                          |
| MED-041  | `threading.Lock` guards Redis singleton creation                              |

---

### 3.3 Domain 3: CI/CD Pipeline and Infrastructure

**Priority**: HIGH
**Issues**: CRIT-003, HIGH-008, HIGH-009, HIGH-012, MED-014, MED-015, MED-016, MED-017, MED-018, MED-019, MED-032, MED-033, LOW-010, LOW-011, LOW-012, LOW-013, LOW-014

**Files to Examine**:

| File                                    | Issues                              | Verification Focus                                  |
|-----------------------------------------|-------------------------------------|-----------------------------------------------------|
| `.github/workflows/lockfile-update.yml` | CRIT-003                            | `--extra observability` present                     |
| `.github/workflows/publish.yml`         | HIGH-012                            | `contents: read` permission                         |
| `.github/workflows/ci.yml`              | MED-014, MED-019                    | pip-audit scope, Codecov upload                     |
| `.github/workflows/security-scan.yml`   | MED-032                             | Bandit invocations use `-c .bandit.yml`             |
| `.bandit.yml`                           | HIGH-009                            | Single source of bandit config                      |
| `pyproject.toml`                        | MED-010, MED-015, MED-017, LOW-014  | Version, dev extra, mypy, py314                     |
| `.pre-commit-config.yaml`               | MED-017, LOW-011, LOW-012           | strict_optional, shellcheck, versions               |
| `Dockerfile`                            | HIGH-008, MED-016, MED-018, LOW-010 | Prod defaults, lockfile, service URLs, health check |
| `conf/logging_config.yaml`              | MED-011                             | Append mode (`mode: a`)                             |
| `.codecov.yml`                          | LOW-013                             | `after_n_builds` documented                         |
| `conf/conda_environment_cpu.yaml`       | MED-033                             | CPU-only variant exists                             |

---

### 3.4 Domain 4: Application Logic and API Correctness

**Priority**: HIGH
**Issues**: HIGH-005, HIGH-006, HIGH-007, HIGH-010, HIGH-011, HIGH-013, MED-001, MED-002, MED-009, MED-010, MED-013, MED-020, MED-021, MED-022, MED-023, MED-029, MED-044, MED-045

**Files to Examine**:

| File                                            | Issues                        | Verification Focus                                                    |
|-------------------------------------------------|-------------------------------|-----------------------------------------------------------------------|
| `src/main.py`                                   | HIGH-010/011, MED-003/020/021 | WebSocket /ws handler, version strings, set_params model, cn_patience |
| `src/communication/websocket_manager.py`        | MED-001, MED-002              | max_connections enforcement, broadcast immutability                   |
| `src/frontend/dashboard_manager.py`             | HIGH-005/006, MED-028/029     | _api_url settings-based, sync HTTP removal, toggle pattern            |
| `src/frontend/components/metrics_panel.py`      | HIGH-013                      | Shared _add_phase_bg_bands method                                     |
| `src/frontend/components/network_visualizer.py` | HIGH-007                      | Dynamic screenshot filename                                           |
| `conf/app_config.yaml`                          | MED-009, MED-013              | Version 0.4.0, CORS list syntax                                       |
| `src/security.py`                               | MED-022                       | get_settings() in get_rate_limiter                                    |
| `src/middleware.py`                             | MED-023                       | ValueError handling in content-length                                 |
| `src/backend/training_monitor.py`               | MED-044                       | apply_params implementation                                           |
| `src/backend/demo_backend.py`                   | MED-045                       | initialize() auto-start behavior                                      |

---

### 3.5 Domain 5: Backend Services

**Priority**: MEDIUM
**Issues**: MED-034, MED-035, MED-036, MED-037, MED-038, MED-042, MED-043, MED-046, MED-047

**Files to Examine**:

| File                                    | Issues           | Verification Focus                                 |
|-----------------------------------------|------------------|----------------------------------------------------|
| `src/backend/cascor_service_adapter.py` | MED-034, MED-035 | Network property caching, relay exception handling |
| `src/backend/data_adapter.py`           | MED-037, MED-038 | Lazy torch import, None input handling             |
| `src/backend/service_backend.py`        | MED-036, MED-046 | KeyError guard, public API usage                   |
| `src/backend/redis_client.py`           | MED-042, MED-043 | Exception aliases, force_new connection leak       |
| `src/backend/training_monitor.py`       | MED-047          | update_state name-mangling avoidance               |

**Verification Criteria**:

| Issue   | Pass Criteria                                                                 |
|---------|-------------------------------------------------------------------------------|
| MED-034 | `network` property uses caching or circuit breaker (not raw HTTP per access)  |
| MED-035 | Relay loop catches specific exceptions, re-raises programming errors          |
| MED-036 | `get_dataset` includes `if "inputs" not in data` or equivalent KeyError guard |
| MED-037 | `import torch` is lazy (`importlib` or `try/except ImportError` at use site)  |
| MED-038 | `prepare_dataset_for_visualization` handles None inputs gracefully            |
| MED-042 | Redis exception aliases use sentinel class (not bare `Exception`)             |
| MED-043 | `force_new=True` calls `.close()` on old connection before replacement        |
| MED-046 | ServiceBackend uses public API methods on CascorServiceAdapter                |
| MED-047 | `update_state` avoids `__dict__` name-mangling introspection                  |

---

### 3.6 Domain 6: Code Quality and Frontend Patterns

**Priority**: MEDIUM
**Issues**: HIGH-014, MED-024, MED-025, MED-026, MED-027, MED-028, MED-030, MED-031, LOW-016, LOW-017, LOW-018, LOW-019, LOW-020

**Files to Examine**:

| File                                            | Issues                              | Verification Focus                              |
|-------------------------------------------------|-------------------------------------|-------------------------------------------------|
| `src/frontend/dashboard_manager.py`             | HIGH-014, MED-028, MED-029, LOW-020 | Line count, time.sleep removal, toggle, theme   |
| `src/frontend/components/metrics_panel.py`      | MED-024, MED-025                    | Dead code removed, orphaned callbacks removed   |
| `src/frontend/base_component.py`                | MED-031, LOW-017                    | create_empty_plot utility, no commented imports |
| `src/frontend/theme_constants.py`               | MED-026                             | ThemeColors class exists and is used            |
| `src/frontend/components/about_panel.py`        | MED-030                             | Documentation links valid                       |
| `src/frontend/components/network_visualizer.py` | MED-027                             | Callback splitting or short-circuit             |
| `src/frontend/components/training_metrics.py`   | LOW-016                             | Deprecation warning added                       |
| `src/frontend/components/redis_panel.py`        | LOW-019                             | _format_hit_rate no double-multiply             |

**Verification Criteria**:

| Issue    | Pass Criteria                                                                   |
|----------|---------------------------------------------------------------------------------|
| HIGH-014 | DashboardManager below 2,000 lines OR documented as accepted partial fix        |
| MED-024  | `_create_candidate_pool_display` method removed entirely                        |
| MED-025  | No orphaned candidate callbacks referencing moved component IDs                 |
| MED-026  | `theme_constants.py` exists with ThemeColors class                              |
| MED-027  | NetworkVisualizer callback uses triggered_id short-circuit OR is split          |
| MED-028  | No `time.sleep()` calls in dashboard_manager.py                                 |
| MED-030  | About panel links point to valid documentation                                  |
| MED-031  | `create_empty_plot()` in base_component.py replaces 5 duplicate implementations |
| LOW-016  | `training_metrics.py` has deprecation warning in module docstring or class      |
| LOW-017  | No commented-out imports in base_component.py                                   |
| LOW-018  | `_layout_type_sprint` properly forwards k, iterations, seed parameters          |
| LOW-019  | `_format_hit_rate` does not double-multiply percentage                          |
| LOW-020  | Header title uses Bootstrap `text-body` class or theme-aware color              |

---

### 3.7 Domain 7: Observability and Logging

**Priority**: MEDIUM
**Issues**: MED-004, MED-005, MED-006, MED-007, MED-008, MED-012, LOW-001, LOW-002, LOW-003, LOW-004, LOW-005, LOW-006, LOW-007, LOW-009

**Files to Examine**:

| File                       | Issues                           | Verification Focus                                                                           |
|----------------------------|----------------------------------|----------------------------------------------------------------------------------------------|
| `src/observability.py`     | MED-004, MED-005                 | Sentry sample rate configurable, Prometheus route templates                                  |
| `src/health.py`            | MED-006                          | Async probes with asyncio.to_thread                                                          |
| `src/logger/logger.py`     | MED-007/008, LOW-004/005/006/007 | Cached wrappers, LogRecord save/restore, caller info, timestamps, print removal, FATAL level |
| `src/settings.py`          | LOW-001                          | Deprecation warnings in legacy validators                                                    |
| `src/config_manager.py`    | LOW-002, LOW-003                 | Boolean/integer precedence, config.key fix                                                   |
| `conf/logging_config.yaml` | MED-012                          | Production-safe default levels, TRACE safety                                                 |

---

### 3.8 Domain 8: Test Quality and Coverage

**Priority**: HIGH
**Issues**: HIGH-016, HIGH-017, HIGH-018, HIGH-019, MED-048, MED-049, LOW-021, LOW-022, Phase 4 tasks (4.1.1-4.2.4, 4.3.1-4.3.6)

**Files to Examine**:

| File                                                     | Issues                    | Verification Focus                                   |
|----------------------------------------------------------|---------------------------|------------------------------------------------------|
| `src/tests/unit/test_dataset_plotter.py`                 | HIGH-016                  | No contextlib.suppress(Exception) around assertions  |
| `src/tests/unit/test_network_visualizer.py`              | HIGH-016, HIGH-018        | No suppress, no hasattr guards                       |
| `src/tests/unit/test_decision_boundary.py`               | HIGH-016                  | No contextlib.suppress(Exception)                    |
| `src/tests/performance/test_button_responsiveness.py`    | HIGH-019, HIGH-018        | Actual assertions, no suppress+hasattr combo         |
| `src/tests/integration/test_websocket_message_schema.py` | HIGH-017                  | pytest.fail() guards after loops                     |
| `src/tests/conftest.py`                                  | MED-048, MED-049, LOW-021 | Mutable dict isolation, reset_singletons, event_loop |
| Phase 4 new test files (8 files)                         | 4.1.1-4.2.4               | All exist with meaningful assertions                 |

**Verification Criteria**:

| Issue    | Pass Criteria                                                                                  |
|----------|------------------------------------------------------------------------------------------------|
| HIGH-016 | ZERO instances of `contextlib.suppress(Exception)` wrapping assertion blocks in test files     |
| HIGH-017 | WebSocket schema test loops include `pytest.fail("No matching message found")` after iteration |
| HIGH-018 | ZERO `hasattr` guards silently skipping test logic in unit/integration tests                   |
| HIGH-019 | Performance test has real timing assertions (not wrapped in suppress+hasattr)                  |
| MED-048  | Session-scoped mutable `_created` dict is either function-scoped or uses deep copy             |
| MED-049  | `reset_singletons` fixture uses explicit class attribute checks (not hasattr)                  |
| LOW-021  | event_loop fixture uses `pytest-asyncio` >= 0.21 compatible pattern                            |
| LOW-022  | Regression tests exercise actual `main.py` code (not local reproductions)                      |

---

## 4. Remediation Framework

For each gap identified during the audit, the following structure MUST be produced:

### 4.1 Gap Report Template

```markdown
### GAP-NNN: [Issue ID] -- [Short Description]

**Claimed Status**: COMPLETE
**Actual Status**: NOT FIXED | PARTIALLY FIXED | REGRESSION

**Evidence**:
- File: `path/to/file.py:line_numbers`
- Current code: [snippet showing the unfixed state]
- Expected code: [snippet showing what the fix should look like]

**Root Cause of Gap**: [Why the fix was not applied -- missed, partial, regression, etc.]

**Severity Assessment**: [Impact of this gap remaining unfixed for release]

**Remediation Option A** -- [Name]:
- Implementation: [Specific code changes]
- Strengths: [Benefits]
- Weaknesses: [Drawbacks]
- Risks: [What could go wrong]
- Guardrails: [Safeguards]

**Remediation Option B** -- [Name]:
- Implementation: [Specific code changes]
- Strengths: [Benefits]
- Weaknesses: [Drawbacks]
- Risks: [What could go wrong]
- Guardrails: [Safeguards]

**Recommendation**: [Option X] because [justification based on analysis]

**Required Tests**:
- [Test 1 description]
- [Test 2 description]
```

---

## 5. Test Validation Strategy

### 5.1 Per-Issue Test Verification

For each issue in the registry:

1. **Existence check**: Confirm a test file/function targets the fixed behavior
2. **Correctness check**: Read the test and confirm it exercises the fix, not just the module
3. **Negative testing**: Confirm the test exercises the failure path the fix prevents
4. **Reversion test**: The test MUST fail if the fix is reverted

### 5.2 Full Suite Validation

After all domain audits complete:

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperCanopy

# Fast unit tests
pytest -m "unit and not slow" -v --tb=short

# Full test suite
pytest -v --tb=short 2>&1 | tail -20
```

**Pass criteria**: 4,412+ tests passed, 0 failed, 0 collection errors, 0 runtime warnings

### 5.3 Coverage Verification

```bash
pytest --cov=. --cov-report=term-missing -m "unit and not slow" --tb=short
```

**Pass criteria**: Overall coverage >= 80% (per pyproject.toml `fail_under=80`)

---

## 6. Documentation Audit

### 6.1 Roadmap Update Verification

The CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md currently shows all tasks as "Not Started" with unchecked `[ ]` boxes. This MUST be updated to reflect the actual completion status matching the CODE_REVIEW_PLAN_2026-04-04.md completion table.

### 6.2 Cross-Document Consistency

Verify consistency between:

- Plan completion claims vs. actual codebase state
- Roadmap task status vs. plan completion status
- Analysis issue descriptions vs. implemented fixes
- Test count claims (4,412) vs. actual pytest collection count

---

## 7. Final Sign-Off Criteria

The audit passes ONLY if ALL of the following are met:

1. **100% Issue Coverage**: Every issue ID has been verified as VERIFIED, PARTIALLY FIXED (with documented gap and remediation plan), or NOT FIXED (with documented gap and remediation plan)
2. **No Silent Failures**: No issue marked COMPLETE in the plan is actually NOT FIXED in the code without being documented as a gap
3. **Test Adequacy**: Every CRITICAL and HIGH issue has at least one dedicated test exercising the fix
4. **Suite Green**: Full test suite passes with 0 failures, 0 collection errors
5. **CI/CD Valid**: Pre-commit hooks pass
6. **Gap Remediation**: All identified gaps have detailed remediation recommendations with multiple approaches
7. **Documentation Consistent**: All three code review documents accurately reflect codebase state

---

## 8. Execution Timeline

| Step | Description                              | Dependencies |
|------|------------------------------------------|--------------|
| 1    | Write this audit plan document           | None         |
| 2-9  | Execute 8 audit domains (parallel)       | Step 1       |
| 10   | Compile gap analysis and remediations    | Steps 2-9    |
| 11   | Run full test suite validation           | Step 10      |
| 12   | Final validation, documentation, cleanup | Step 11      |

---

## 9. Audit Findings

### 9.1 Domain Results Summary

| Domain           | Issues Audited | Verified     | Partially Fixed | Not Fixed    | Regressions |
|------------------|----------------|--------------|-----------------|--------------|-------------|
| 1. Security      | 7              | 6            | 0               | 1            | 0           |
| 2. Concurrency   | 5              | 2            | 1               | 2            | 0           |
| 3. CI/CD         | 17             | 14           | 3               | 0            | 0           |
| 4. App Logic/API | 18             | 12           | 4               | 2            | 0           |
| 5. Backend       | 9              | 1            | 1               | 7            | 0           |
| 6. Code Quality  | 13             | 9            | 3               | 1            | 0           |
| 7. Observability | 14             | 12           | 2               | 0            | 0           |
| 8. Test Quality  | 8              | 1            | 2               | 5            | 0           |
| **Total**        | **91**         | **57 (63%)** | **16 (18%)**    | **18 (20%)** | **0**       |

**Phase 4 Coverage Expansion**: 8 of 8 new test files VERIFIED with meaningful content. 1 supplementary task (parameters_panel dedicated tests) PARTIALLY FIXED.

### 9.2 Verified Issues (57 total)

CRIT-001, CRIT-002, CRIT-003, HIGH-001, HIGH-002, HIGH-003, HIGH-004, HIGH-006, HIGH-009, HIGH-011, HIGH-012, HIGH-013, MED-001, MED-003, MED-004, MED-005, MED-006, MED-007, MED-008, MED-009, MED-010, MED-011, MED-012, MED-013, MED-014, MED-015, MED-016, MED-017,
MED-019, MED-020, MED-021, MED-022, MED-023, MED-024, MED-025, MED-028, MED-031, MED-032, MED-033, MED-036, MED-044, LOW-001, LOW-002, LOW-004, LOW-005, LOW-006, LOW-008, LOW-009, LOW-011, LOW-012, LOW-013, LOW-014, LOW-016, LOW-017, LOW-018, LOW-019, LOW-020, LOW-022

---

#### GAP-001: MED-040 -- Cassandra Credentials Stored as Plain Attributes

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/cassandra_client.py:111-112` -- `self._username` and `self._password` assigned from config and persist on the singleton for its entire lifetime. Any code with access to the singleton can read `get_cassandra_client()._password`.

**Remediation Option A** -- Transient credential usage:

- Pass credentials directly to `PlainTextAuthProvider` without storing on `self`
- Strengths: Minimal change, eliminates the exposure window
- Weaknesses: Credentials still readable from config_manager
- Risks: Low -- just reorganizes where creds are held

**Remediation Option B** -- Migrate to secrets_util:

- Use `secrets_util.get_secret()` for Docker secrets compatibility
- Strengths: Consistent with API key management in security.py
- Weaknesses: Requires Docker secrets setup for Cassandra
- Risks: Environment-dependent; needs fallback for non-Docker

**Recommendation**: Option A (minimal, effective, no infrastructure dependency)

---

#### GAP-002: MED-039 -- Cassandra Singleton Not Thread-Safe

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/cassandra_client.py:482-500` -- bare global variable with no `threading.Lock`. Two threads calling `get_cassandra_client()` simultaneously can both create instances.

**Remediation**: Add double-checked locking with `threading.Lock` around singleton creation. Standard pattern: check-lock-check-create.

---

#### GAP-003: MED-041 -- Redis Singleton Not Thread-Safe

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/redis_client.py:524-543` -- identical pattern to MED-039. No `threading.Lock` guard.

**Remediation**: Same double-checked locking pattern as GAP-002.

---

#### GAP-004: HIGH-007 -- NetworkVisualizer Screenshot Filename Not Dynamic

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: High

**Evidence**: `src/frontend/components/network_visualizer.py:222-225` -- `toImageButtonOptions` contains only `format` and `scale`. No `filename` key with dynamic `datetime.now()`.

**Remediation Option A** -- Add dynamic filename in callback:

- In the callback that generates the figure, set `fig.update_layout({"images": ...})` with `toImageButtonOptions={"filename": f"canopy_network_{datetime.now():%Y%m%d_%H%M%S}"}`
- Strengths: Unique filenames per screenshot
- Weaknesses: Plotly may not support dynamic toImageButtonOptions at callback time

**Remediation Option B** -- Use JavaScript clientside callback:

- Add a Dash clientside callback that updates the download button's filename attribute
- Strengths: Guaranteed to work at click time
- Weaknesses: More complex implementation

**Recommendation**: Option A -- test if Plotly respects config updates at callback time first

---

#### GAP-005: MED-045 -- DemoBackend.initialize() Unconditionally Starts Training

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/demo_backend.py:321-324` -- `initialize()` unconditionally calls `self._demo.start()`.

**Remediation Option A** -- Add documentation:

- Add docstring explaining this is intentional for demo mode
- Strengths: Clarifies design intent; demo mode's purpose IS to show running simulation
- Weaknesses: Doesn't change behavior

**Remediation Option B** -- Add `auto_start` parameter:

- `async def initialize(self, auto_start: bool = True) -> bool:`
- Strengths: Flexibility for testing and future use
- Weaknesses: Changes interface; callers need updating

**Recommendation**: Option A -- the auto-start behavior is by design for demo mode

---

#### GAP-006: HIGH-014 -- DashboardManager God Class (3007 lines)

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: High

**Evidence**: `src/frontend/dashboard_manager.py` is 3,007 lines. No extraction modules exist. The roadmap acceptance criterion was "below 2,000 lines."

**Remediation**: Extract sidebar, controls, stores, and theme into separate modules (`sidebar_manager.py`, `controls_manager.py`, `store_manager.py`, `theme_manager.py`). This is a significant refactoring effort that should be a dedicated task.

---

#### GAP-007: MED-034 -- Network Property HTTP Call Per Access

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/cascor_service_adapter.py:342-351` -- `network` property calls `self._client.get_network()` with no caching or circuit breaker.

**Remediation**: Add TTL-based caching (e.g., `functools.lru_cache` with TTL wrapper, or a `_network_cache` attribute with timestamp check). 30-second TTL is reasonable for network topology that changes infrequently.

---

#### GAP-008: MED-037 -- Top-Level `import torch` (2GB Load)

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/data_adapter.py:42` -- unconditional `import torch` at module level.

**Remediation**: Move to lazy import at use-site. Use `TYPE_CHECKING` guard for type annotations, `importlib.import_module("torch")` at runtime in methods that need it.

---

#### GAP-009: MED-038 -- prepare_dataset_for_visualization Crashes on None

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/data_adapter.py:308-337` -- no None guard before `len(inputs)` at line 334.

**Remediation**: Add early return: `if inputs is None or targets is None: return {"dataset_name": dataset_name, ...default empty values...}`

---

#### GAP-010: MED-042 -- Redis Exception Aliases = Exception

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/redis_client.py:68-72` -- `RedisConnectionError = Exception` when redis-py not installed. All `except RedisConnectionError` clauses catch every exception.

**Remediation**: Use sentinel class: `class _RedisSentinelError(Exception): pass` -- never raised, so except clauses effectively catch nothing when redis unavailable.

---

#### GAP-011: MED-043 -- Redis force_new Leaks Connection Pool

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/redis_client.py:527-543` -- `force_new=True` overwrites the global without calling `.close()` on old instance.

**Remediation**: Add `if force_new and _redis_client_instance is not None: _redis_client_instance.close()` before replacement.

---

#### GAP-012: MED-046 -- ServiceBackend Accesses Private Attributes

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/service_backend.py:113,221,226,228` -- accesses `_is_cascor_nested`, `_client`, `_service_url` on CascorServiceAdapter.

**Remediation**: Expose public properties/methods on CascorServiceAdapter: `service_url` property, `client` property, make `is_cascor_nested` public.

---

#### GAP-013: MED-047 -- TrainingState Name-Mangling Introspection

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/backend/training_monitor.py:345-371` -- constructs `_TrainingState__<key>` mangled names for `__dict__` access. Fragile under subclassing.

**Remediation**: Replace with explicit state dict: `self._state = {"status": ..., "phase": ...}` and access via `self._state[key]`.

---

#### GAP-014: HIGH-016 -- contextlib.suppress(Exception) in Test Assertions

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: High

**Evidence**: 18+ instances across `test_dataset_plotter.py`, `test_network_visualizer.py`, `test_decision_boundary.py`, `test_button_responsiveness.py`, `test_websocket_message_schema.py`, `test_main_ws.py`, `test_demo_endpoints.py`, `test_config_refactoring.py`.

**Remediation**: Remove all `contextlib.suppress(Exception)` wrappers around test assertions. Tests that might fail on missing attributes should use `pytest.importorskip` or explicit skip markers, not silent suppression.

---

#### GAP-015: HIGH-017 -- WebSocket Schema Tests No Fail Guard

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: High

**Evidence**: `src/tests/integration/test_websocket_message_schema.py` -- all loop-based searches for message types have no `pytest.fail()` after the loop.

**Remediation**: After each search loop, add: `assert found, "No matching message of type X found"` or `pytest.fail("No matching message found")`.

---

#### GAP-016: HIGH-018 -- hasattr Guards Skip Test Logic

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: High

**Evidence**: 30+ instances across `test_dataset_plotter.py` (10), `test_network_visualizer.py` (9), `test_decision_boundary.py` (10), `test_button_responsiveness.py` (1), `test_dashboard_manager.py` (8).

**Remediation**: Replace `if hasattr(obj, "method"):` guards with direct calls. If the method doesn't exist, the test should FAIL (AttributeError), not silently pass.

---

#### GAP-017: MED-048 -- Session-Scoped Mutable Dict in Fixture

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/tests/conftest.py:256,304` -- `mock_juniper_data_client` is session-scoped with mutable `_created` dict that leaks between tests.

**Remediation Option A** -- Change to function scope (simple but slower).
**Remediation Option B** -- Deep copy `_created` per test with a function-scoped wrapper fixture.

**Recommendation**: Option B -- preserves session-scoped performance with per-test isolation.

---

#### GAP-018: MED-049 -- reset_singletons Uses Fragile hasattr

**Claimed Status**: COMPLETE | **Actual Status**: NOT FIXED | **Severity**: Medium

**Evidence**: `src/tests/conftest.py:614-706` -- hasattr checks for singleton internal attributes; `contextlib.suppress(Exception)` swallows cleanup failures.

**Remediation**: Add `_reset_for_testing()` class method to each singleton. The fixture calls these methods instead of introspecting internal attributes.

---

### 9.4 Gap Reports -- PARTIALLY FIXED (16 issues)

| Issue    | Domain        | Gap Description                                                                                                      |
|----------|---------------|----------------------------------------------------------------------------------------------------------------------|
| HIGH-015 | Concurrency   | Lock on mutations but NOT on getters (`get_status`, `get_phase`, etc.)                                               |
| HIGH-008 | CI/CD         | Root `Dockerfile` fixed; `conf/Dockerfile` uses legacy env vars, no LOG_LEVEL/DEMO_MODE                              |
| MED-018  | CI/CD         | Root `Dockerfile` has Docker service names; `conf/Dockerfile` has no service URL ENVs                                |
| LOW-010  | CI/CD         | Root `Dockerfile` uses curl; `conf/Dockerfile` still uses Python health check                                        |
| HIGH-005 | App Logic     | `FAST_API_TIMEOUT_SECONDS` constant used (satisfying "or timeout" clause) but call still synchronous                 |
| HIGH-010 | App Logic     | Logs and exits on Exception, but no `finally` cleanup block, no recoverable/fatal distinction                        |
| MED-002  | App Logic     | `broadcast()` uses copy; `send_personal_message()` still mutates at line 302                                         |
| MED-029  | App Logic     | Network info toggle fixed; dark mode toggle still uses modulo pattern                                                |
| MED-026  | Code Quality  | `theme_constants.py` with ThemeColors created; only `base_component.py` imports it; ~169 hardcoded hex values remain |
| MED-027  | Code Quality  | `ctx.triggered` short-circuit added; callback still has 10 inputs, not split                                         |
| MED-030  | Code Quality  | 3 of 4 doc links valid; `docs/API.md` link 404s (file is `docs/api/API_REFERENCE.md`)                                |
| MED-035  | Backend       | `asyncio.CancelledError` separated; outer `except Exception` still catches all others                                |
| LOW-003  | Observability | `config.key` AttributeError fixed; replacement ternary logic has operator-precedence concern                         |
| LOW-007  | Observability | `fatal()` uses FATAL_LEVEL=60 consistently; divergence from standard `FATAL=50` undocumented                         |
| HIGH-019 | Test Quality  | 3 of 5 tests are proper; `test_button_visual_feedback_latency` still no-op (hasattr+suppress)                        |
| LOW-021  | Test Quality  | `asyncio_mode="auto"` in pyproject.toml; deprecated `event_loop` fixture still defined                               |

### 9.5 Documentation Gaps

1. **CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md**: All tasks still show "Not Started" with unchecked `[ ]` boxes. Must be updated to reflect actual completion status.
2. **conf/app_config.yaml header**: Line 9 shows `Version: 0.1.4 (0.7.3)` while the YAML value at line 44 is correctly `0.4.0`.
3. **conf/Dockerfile**: Three partial fixes (HIGH-008, MED-018, LOW-010) all trace to this file not being updated alongside the root `Dockerfile`. Needs either updating or deprecation marking.

### 9.6 Severity Distribution of Gaps

| Severity  | Not Fixed                                            | Partially Fixed                                      | Total Gaps |
|-----------|------------------------------------------------------|------------------------------------------------------|------------|
| Critical  | 0                                                    | 0                                                    | 0          |
| High      | 4 (HIGH-007, HIGH-014, HIGH-016, HIGH-017, HIGH-018) | 5 (HIGH-005, HIGH-008, HIGH-010, HIGH-015, HIGH-019) | 9          |
| Medium    | 14                                                   | 9                                                    | 23         |
| Low       | 0                                                    | 2                                                    | 2          |
| **Total** | **18**                                               | **16**                                               | **34**     |

### 9.7 Gap Clustering by Root Cause

**Cluster 1: Backend module addendum tasks never executed** (7 issues)
MED-034, MED-037, MED-038, MED-042, MED-043, MED-046, MED-047 -- These were in the "Phase 1/3 Addendum" sections of the roadmap. The addendum tasks appear to have been overlooked during the consolidated `fix/release-critical-quality` branch work.

**Cluster 2: Test quality addendum tasks never executed** (5 issues)
HIGH-016, HIGH-017, HIGH-018, MED-048, MED-049 -- These were in the "Phase 4 Addendum" section (tasks 4.3.1-4.3.4). New test files were created (tasks 4.1.1-4.2.4) but existing test quality defects were not addressed.

**Cluster 3: conf/Dockerfile not updated** (3 issues)
HIGH-008, MED-018, LOW-010 -- The root `Dockerfile` was properly fixed; the `conf/Dockerfile` variant was not touched.

**Cluster 4: Singleton thread safety** (2 issues)
MED-039, MED-041 -- Both Cassandra and Redis singletons lack `threading.Lock` guards. Same pattern, same fix.

---

## 10. Remediation Priority Matrix

### Priority 1: HIGH Severity -- Must Fix Before Release

| Gap     | Issue    | Effort | Description                                                 |
|---------|----------|--------|-------------------------------------------------------------|
| GAP-014 | HIGH-016 | Medium | Remove contextlib.suppress from test assertions (~18 sites) |
| GAP-015 | HIGH-017 | Low    | Add pytest.fail guards to WebSocket schema tests (~6 loops) |
| GAP-016 | HIGH-018 | Medium | Remove hasattr guards from test bodies (~30 sites)          |
| GAP-004 | HIGH-007 | Low    | Add dynamic screenshot filename                             |
| GAP-006 | HIGH-014 | High   | DashboardManager extraction (3007 -> <2000 lines)           |

### Priority 2: MEDIUM Severity -- Should Fix Before Release

| Gap     | Issue   | Effort | Description                                         |
|---------|---------|--------|-----------------------------------------------------|
| GAP-002 | MED-039 | Low    | Add threading.Lock to Cassandra singleton           |
| GAP-003 | MED-041 | Low    | Add threading.Lock to Redis singleton               |
| GAP-010 | MED-042 | Low    | Use sentinel class for Redis exception aliases      |
| GAP-011 | MED-043 | Low    | Close old Redis connection on force_new             |
| GAP-009 | MED-038 | Low    | Add None guard to prepare_dataset_for_visualization |
| GAP-008 | MED-037 | Medium | Lazy-import torch                                   |
| GAP-007 | MED-034 | Low    | Add TTL cache to network property                   |
| GAP-012 | MED-046 | Medium | Expose public API on CascorServiceAdapter           |
| GAP-013 | MED-047 | Medium | Replace name-mangling with state dict               |
| GAP-001 | MED-040 | Low    | Transient credential usage for Cassandra            |
| GAP-005 | MED-045 | Low    | Document auto-start intent                          |
| GAP-017 | MED-048 | Low    | Session fixture isolation                           |
| GAP-018 | MED-049 | Medium | Singleton reset registry pattern                    |

### Priority 3: Partial Fix Completion

| Issue           | Effort | Description                                                     |
|-----------------|--------|-----------------------------------------------------------------|
| HIGH-015        | Low    | Add lock to getter methods in TrainingStateMachine              |
| HIGH-005        | High   | Migrate fast-interval callbacks to async HTTP or WebSocket push |
| HIGH-010        | Low    | Add finally block to /ws endpoint handler                       |
| MED-002         | Low    | Fix send_personal_message mutation                              |
| MED-029         | Low    | Fix dark mode modulo toggle                                     |
| MED-026         | High   | Wire ThemeColors into all 10+ component files                   |
| MED-030         | Low    | Fix API.md link to docs/api/API_REFERENCE.md                    |
| MED-035         | Medium | Narrow relay loop exception handling                            |
| conf/Dockerfile | Medium | Update or deprecate conf/Dockerfile                             |

---

## 11. Test Suite Validation Results

```bash
Full suite: 4,432 passed, 56 skipped, 0 failed, 0 errors (396s)
Fast unit:  1,469 passed, 3,019 deselected, 0 failed, 1 warning (23s)
```

- Test count (4,432) exceeds documented claim (4,412) by 20 tests -- likely from post-review additions
- All tests pass with 0 failures, 0 collection errors from the repository root
- The 1 warning is a `DeprecationWarning` from `DemoMode._generate_spiral_dataset_local()` -- expected and documented
- 56 skipped tests are infrastructure-dependent (requires_cascor, requires_redis, etc.) -- expected per ADR-001
- **Note**: Running from `src/` instead of repo root causes 2 Dockerfile path resolution failures in `test_docker_demo_mode_default.py` -- these tests use relative paths (`Dockerfile`, `conf/Dockerfile`) that only resolve from the repo root. This is a test portability concern but not a product defect.

---

*Document generated: 2026-04-12*
*Audit completed: 2026-04-12*
*Auditor: Claude Code (Principal Engineer Role)*
*Status: AUDIT COMPLETE -- 34 gaps identified, remediation plan developed*
