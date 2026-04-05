# Juniper Canopy -- Code Review Remediation Plan

**Date**: 2026-04-04
**Version**: 0.4.0
**Companion Document**: [CODE_REVIEW_ANALYSIS_2026-04-04.md](CODE_REVIEW_ANALYSIS_2026-04-04.md)

---

## Overview

This plan outlines the phased approach to remediating all issues identified in the comprehensive code review analysis. Work is organized into 5 phases by priority, with each phase containing discrete steps and tasks. Dependencies between tasks are noted.

---

## Phase 0: Pre-Release Blockers (Security & Concurrency)

**Priority**: IMMEDIATE -- Must complete before any release
**Estimated Scope**: 6 tasks, ~8 files modified
**Branch**: `fix/pre-release-security-audit`

### Step 0.1: Fix Security Vulnerabilities

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 0.1.1 | CRIT-001 | `src/main.py` | Add snapshot name sanitization and path confinement |
| 0.1.2 | HIGH-001 | `src/security.py` | Replace set membership with `hmac.compare_digest()` |
| 0.1.3 | HIGH-002 | `src/main.py` | Suppress internal details in global exception handler |
| 0.1.4 | HIGH-003 | `src/security.py` | Add periodic eviction to rate limiter counters |

**Verification**:

- [ ] Write security-focused test for path traversal with `../../`, `..\\`, URL-encoded sequences
- [ ] Write timing attack test verifying constant-time comparison
- [ ] Write test confirming generic error messages for unhandled exceptions
- [ ] Write test confirming rate limiter memory stays bounded under load
- [ ] Run full test suite -- 0 failures

### Step 0.2: Fix Concurrency Issues

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 0.2.1 | CRIT-002 | `src/frontend/callback_context.py` | Replace instance attributes with `contextvars.ContextVar` |
| 0.2.2 | HIGH-004 | `src/demo_mode.py` | Use `_stop.clear()` instead of `_stop = Event()` |

**Verification**:

- [ ] Write concurrent callback test verifying thread isolation
- [ ] Write test for stop/reset/start rapid cycling
- [ ] Run full test suite -- 0 failures

---

## Phase 1: Release-Critical Fixes (Architecture, Logic, Config)

**Priority**: HIGH -- Complete before release
**Estimated Scope**: 14 tasks, ~15 files modified
**Branch**: `fix/release-critical-quality`

### Step 1.1: Fix API and WebSocket Issues

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 1.1.1 | HIGH-010 | `src/main.py` | Fix `/ws` exception handling -- distinguish recoverable/fatal, add `finally` |
| 1.1.2 | MED-001 | `src/communication/websocket_manager.py` | Enforce `max_connections` in `connect()` |
| 1.1.3 | MED-002 | `src/communication/websocket_manager.py` | Copy message dict before mutation |
| 1.1.4 | MED-020 | `src/main.py` | Remove duplicate `cn_patience` in parameter list |
| 1.1.5 | MED-021 | `src/main.py` | Define Pydantic model for `set_params` request body |
| 1.1.6 | MED-023 | `src/middleware.py` | Handle `ValueError` in content-length parsing |
| 1.1.7 | MED-003 | `src/main.py` | Restrict CORS methods and headers |

**Verification**:

- [ ] WebSocket connection limit test
- [ ] Message immutability test
- [ ] Parameter validation test with invalid keys
- [ ] Content-Length fuzzing test
- [ ] Run full test suite -- 0 failures

### Step 1.2: Fix Configuration Consistency

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 1.2.1 | HIGH-011 | `src/main.py` | Replace hardcoded versions with `importlib.metadata.version()` |
| 1.2.2 | MED-009 | `conf/app_config.yaml` | Update `application.version` to 0.4.0 |
| 1.2.3 | MED-010 | `pyproject.toml` | Update header comment version |
| 1.2.4 | MED-022 | `src/security.py` | Use `get_settings()` in `get_rate_limiter()` |
| 1.2.5 | MED-013 | `conf/app_config.yaml` | Fix CORS `allowed_origins` YAML syntax |

**Verification**:

- [ ] Version consistency test across all endpoints
- [ ] Rate limiter settings integration test
- [ ] CORS configuration parsing test
- [ ] Run full test suite -- 0 failures

### Step 1.3: Fix Frontend Critical Issues

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 1.3.1 | HIGH-006 | `src/frontend/dashboard_manager.py` | Replace `_api_url()` with settings-based URL |
| 1.3.2 | HIGH-007 | `src/frontend/components/network_visualizer.py` | Fix static screenshot timestamp |
| 1.3.3 | HIGH-013 | `src/frontend/components/metrics_panel.py` | Refactor accuracy plot to use shared phase band methods |

**Verification**:

- [ ] API URL construction test (no request context dependency)
- [ ] Visual regression check on metrics plots
- [ ] Run full test suite -- 0 failures

---

## Phase 2: CI/CD and Infrastructure (Pipeline Reliability)

**Priority**: HIGH -- Complete before or alongside release
**Estimated Scope**: 12 tasks, ~10 files modified
**Branch**: `fix/ci-cd-infrastructure`

### Step 2.1: Fix CI Pipeline Issues

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 2.1.1 | CRIT-003 | `.github/workflows/lockfile-update.yml` | Add `--extra observability` to lockfile compilation |
| 2.1.2 | HIGH-012 | `.github/workflows/publish.yml` | Add `contents: read` permission |
| 2.1.3 | MED-014 | `.github/workflows/ci.yml` | Replace ad-hoc pip install with full project install for pip-audit |
| 2.1.4 | MED-015 | `pyproject.toml` | Define `[project.optional-dependencies] dev` extra |
| 2.1.5 | MED-019 | `.github/workflows/ci.yml` | Add `codecov/codecov-action` step |

### Step 2.2: Fix Security Scanning

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 2.2.1 | HIGH-009 | `.bandit.yml`, `pyproject.toml`, `.pre-commit-config.yaml` | Consolidate bandit config to single source |
| 2.2.2 | MED-032 | `.github/workflows/security-scan.yml` | Add explicit `-c .bandit.yml` to all invocations |
| 2.2.3 | MED-017 | `.pre-commit-config.yaml` | Remove `--no-strict-optional` from mypy hook |

### Step 2.3: Fix Docker Configuration

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 2.3.1 | HIGH-008 | `conf/app_config.yaml`, `Dockerfile` | Create production config or ensure env var overrides |
| 2.3.2 | MED-016 | `Dockerfile`, `pyproject.toml` | Add missing packages to pyproject.toml, regenerate lockfile |
| 2.3.3 | MED-018 | `Dockerfile` | Change default service URLs to Docker service names |
| 2.3.4 | MED-011 | `conf/logging_config.yaml` | Change file handler mode to `a` |

**Verification**:

- [ ] Dependabot PR passes CI (simulate with lockfile-update workflow)
- [ ] Bandit produces identical results from all invocation paths
- [ ] Docker build succeeds with production config
- [ ] Docker health check passes
- [ ] Run full test suite -- 0 failures

---

## Phase 3: Code Quality and Observability

**Priority**: MEDIUM -- Complete in next maintenance cycle
**Estimated Scope**: 18 tasks, ~20 files modified
**Branch**: `chore/code-quality-improvements`

### Step 3.1: Fix Logging and Observability

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 3.1.1 | MED-008 | `src/logger/logger.py` | Save/restore LogRecord.levelname in ColoredFormatter |
| 3.1.2 | MED-007 | `src/logger/logger.py` | Cache logger wrapper instances |
| 3.1.3 | MED-004 | `src/observability.py` | Make Sentry sample rate configurable |
| 3.1.4 | MED-005 | `src/observability.py` | Normalize Prometheus endpoint labels |
| 3.1.5 | MED-006 | `src/main.py`, `src/health.py` | Use async probes or `asyncio.to_thread()` |
| 3.1.6 | MED-012 | `conf/logging_config.yaml` | Set production-safe default levels |

### Step 3.2: Remove Dead Code and Duplications

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 3.2.1 | MED-024 | `src/frontend/components/metrics_panel.py` | Remove dead `_create_candidate_pool_display` |
| 3.2.2 | MED-025 | `src/frontend/components/metrics_panel.py` | Remove orphaned candidate callbacks |
| 3.2.3 | MED-031 | Multiple component files | Extract shared `create_empty_plot()` utility |
| 3.2.4 | LOW-016 | `src/frontend/components/training_metrics.py` | Remove legacy component or add deprecation |
| 3.2.5 | LOW-017 | `src/frontend/base_component.py` | Remove commented import |

### Step 3.3: Fix Frontend Patterns

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 3.3.1 | MED-026 | New `src/frontend/theme_constants.py` + all components | Extract hardcoded colors to theme module |
| 3.3.2 | MED-029 | `src/frontend/dashboard_manager.py` | Fix toggle pattern to use `State("...", "is_open")` |
| 3.3.3 | MED-030 | `src/frontend/components/about_panel.py` | Fix or remove broken documentation links |
| 3.3.4 | MED-028 | `src/frontend/dashboard_manager.py` | Remove `time.sleep()` from apply parameters retry |
| 3.3.5 | MED-027 | `src/frontend/components/network_visualizer.py` | Split overloaded callback into focused callbacks |

### Step 3.4: Fix Performance Issues

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| 3.4.1 | HIGH-005 | `src/frontend/dashboard_manager.py` | Reduce API timeout for fast-interval callbacks |
| 3.4.2 | HIGH-014 | `src/frontend/dashboard_manager.py` | Begin extraction of DashboardManager into sub-modules |

**Verification**:

- [ ] Logger output format verification (no ANSI in file handlers)
- [ ] Prometheus cardinality check
- [ ] Theme consistency visual check
- [ ] Run full test suite -- 0 failures

---

## Phase 4: Test Coverage Expansion

**Priority**: MEDIUM -- Parallel with Phase 3
**Estimated Scope**: 8 new test files
**Branch**: `test/coverage-expansion`

### Step 4.1: Fill Coverage Gaps

| Task | Module | Description |
|------|--------|-------------|
| 4.1.1 | `discovery.py` | Write unit tests for service discovery probing |
| 4.1.2 | `observability.py` | Write tests for Prometheus middleware and Sentry config |
| 4.1.3 | `secrets_util.py` | Write tests for SOPS decryption paths |
| 4.1.4 | `middleware.py` | Write edge case tests (malformed headers, oversized bodies) |

### Step 4.2: Add Missing Test Types

| Task | Type | Description |
|------|------|-------------|
| 4.2.1 | Security | Write auth bypass, injection, and CORS validation tests |
| 4.2.2 | Load | Write concurrent WebSocket connection tests |
| 4.2.3 | Resilience | Write circuit breaker failure scenario tests |
| 4.2.4 | Contract | Expand API schema validation tests |

**Verification**:

- [ ] Coverage report shows improvement in gap areas
- [ ] All new tests pass
- [ ] Run full test suite -- 0 failures

---

## Phase 5: Low Priority and Housekeeping

**Priority**: LOW -- Address in regular maintenance
**Estimated Scope**: 19 tasks across minor fixes
**Branch**: `chore/housekeeping`

### Step 5.1: Configuration Cleanup

| Task | Issue | Description |
|------|-------|-------------|
| 5.1.1 | LOW-001 | Add deprecation warnings to remaining legacy env var validators |
| 5.1.2 | LOW-002 | Fix `_convert_type` boolean/integer precedence |
| 5.1.3 | LOW-009 | Migrate `CASCOR_SNAPSHOT_DIR` to `JUNIPER_CANOPY_SNAPSHOT_DIR` |
| 5.1.4 | LOW-014 | Add `py314` to Black target-version when available |
| 5.1.5 | MED-033 | Create CPU-only conda environment for canopy |

### Step 5.2: Logging Cleanup

| Task | Issue | Description |
|------|-------|-------------|
| 5.2.1 | LOW-004 | Fix `_log_with_context` to capture real call site |
| 5.2.2 | LOW-005 | Use timezone-aware timestamps in JsonFormatter |
| 5.2.3 | LOW-006 | Replace print() with logger.debug() |
| 5.2.4 | LOW-007 | Resolve FATAL_LEVEL 60 vs standard 50 conflict |

### Step 5.3: Minor Code Fixes

| Task | Issue | Description |
|------|-------|-------------|
| 5.3.1 | LOW-003 | Fix `config.key` AttributeError in error handler |
| 5.3.2 | LOW-008 | Add message size check to training WebSocket |
| 5.3.3 | LOW-015 | Narrow exception types in callback_context |
| 5.3.4 | LOW-018 | Forward parameters in `_layout_type_sprint` |
| 5.3.5 | LOW-019 | Verify `_format_hit_rate` percentage contract |
| 5.3.6 | LOW-020 | Make header title color theme-aware |

### Step 5.4: CI/CD Housekeeping

| Task | Issue | Description |
|------|-------|-------------|
| 5.4.1 | LOW-010 | Consider curl-based Docker health check |
| 5.4.2 | LOW-011 | Align shellcheck severity to ecosystem convention |
| 5.4.3 | LOW-012 | Run `pre-commit autoupdate` |
| 5.4.4 | LOW-013 | Add comment documenting codecov build count |

---

## Execution Notes

### Dependencies Between Phases

```text
Phase 0 ──must complete before──> Phase 1
Phase 1 ──must complete before──> Phase 2, Phase 3, Phase 4
Phase 2 ──can parallel with──> Phase 3, Phase 4
Phase 3 ──can parallel with──> Phase 4
Phase 5 ──no dependencies──> (anytime)
```

### Git Strategy

- Each phase gets its own branch from `main`
- Phases 0 and 1 are merged via PR before Phase 2 begins
- Phases 2-4 can be worked in parallel with separate PRs
- Phase 5 tasks can be cherry-picked individually

### Testing Requirements

Every phase must end with:

1. Full test suite passes (4,169+ tests, 0 failures)
2. No new warnings introduced
3. Pre-commit hooks pass
4. CI pipeline green

---

*Document generated: 2026-04-04*
*Companion: [CODE_REVIEW_ANALYSIS_2026-04-04.md](CODE_REVIEW_ANALYSIS_2026-04-04.md)*
