# Juniper Canopy -- Code Review Remediation Plan (R5-01 Aligned)

**Date**: 2026-04-12
**Version**: 0.4.0
**Source of Truth**: [R5-01 Canonical Development Plan](../../juniper-ml/notes/interface_proposals/R5-01_canonical_development_plan.md)
**Companion**: [CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md](CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md)
**Supersedes**: [CODE_REVIEW_PLAN_2026-04-04.md](CODE_REVIEW_PLAN_2026-04-04.md)

---

## 1. Overview

This plan restructures the original 5-phase code review remediation plan to coordinate with the R5-01 Canonical Development Plan's 11-phase implementation. The goal is to:

1. **Prevent merge conflicts** with R5-01 phase work
2. **Avoid duplicate work** where R5-01 provides a comprehensive solution
3. **Maintain release blockers** that R5-01 does not address
4. **Leverage R5-01 phases** to implement audit fixes where they overlap

The original plan's 5 phases (0-5) are reorganized into 4 new tracks that run alongside R5-01 phases.

## 2. Track Structure

### Track Diagram

```text
Track PRE  ─── Pre-R5-01 Independent Fixes ─── [No R5-01 dependency]
   │
Track PAR  ─── Parallel with R5-01 ─────────── [Runs alongside R5-01 phases]
   │
Track EMB  ─── R5-01 Phase-Embedded ────────── [Fix done AS PART OF R5-01]
   │
Track POST ─── Post-R5-01 Deferred ─────────── [Waits for R5-01 completion]
```

| Track | Issues | Prerequisite | Blocks |
|-------|--------|--------------|--------|
| PRE | Independent security, concurrency, CI/CD | None | Release readiness |
| PAR | Test quality, logging, observability | None | Release readiness |
| EMB | WS-related, adapter, schema tests | R5-01 phase start | R5-01 phase exit |
| POST | Architecture refactors, theme rollout | R5-01 Phase B stable | Post-release |

## 3. Track PRE: Pre-R5-01 Independent Fixes

**Priority**: IMMEDIATE
**Dependencies**: None
**Blocks**: Release readiness
**Branches**: `fix/release-critical-*`

These are the audit fixes that have no interaction with R5-01. They can be executed in full without waiting for any R5-01 phase.

### Step PRE-1: Critical Security & Concurrency

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PRE-1.1 | CRIT-001 | `src/main.py` | Snapshot name sanitization + path confinement |
| PRE-1.2 | CRIT-002 | `src/frontend/callback_context.py` | contextvars migration |
| PRE-1.3 | HIGH-001 | `src/security.py` | hmac.compare_digest for API keys |
| PRE-1.4 | HIGH-002 | `src/main.py` | Generic exception handler + server-side logging + **CRLF escape** |
| PRE-1.5 | HIGH-003 | `src/security.py` | HTTP rate limiter eviction + emergency cap |
| PRE-1.6 | HIGH-004 | `src/demo_mode.py` | `_stop.clear()` replaces Event replacement |
| PRE-1.7 | HIGH-015 | `src/backend/training_state_machine.py` | Lock on ALL state access (mutations AND getters) |
| PRE-1.8 | MED-039 | `src/backend/cassandra_client.py` | Cassandra singleton threading.Lock |
| PRE-1.9 | MED-040 | `src/backend/cassandra_client.py` | Transient credential usage |
| PRE-1.10 | MED-041 | `src/backend/redis_client.py` | Redis singleton threading.Lock |
| PRE-1.11 | MED-042 | `src/backend/redis_client.py` | Redis sentinel exception class |
| PRE-1.12 | MED-043 | `src/backend/redis_client.py` | Redis force_new connection close |

**Acceptance Criteria**:

- All security and concurrency issues resolved
- Full test suite green
- Pre-commit hooks pass

### Step PRE-2: CI/CD & Configuration

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PRE-2.1 | CRIT-003 | `.github/workflows/lockfile-update.yml` | Add `--extra observability` |
| PRE-2.2 | HIGH-008 | `Dockerfile` | Production defaults (**root Dockerfile ONLY**; `conf/Dockerfile` in POST track) |
| PRE-2.3 | HIGH-009 | `.bandit.yml`, `pyproject.toml` | Consolidate bandit config |
| PRE-2.4 | HIGH-012 | `.github/workflows/publish.yml` | Add `contents: read` permission |
| PRE-2.5 | MED-014 | `.github/workflows/ci.yml` | pip-audit full scan |
| PRE-2.6 | MED-015 | `pyproject.toml` | Define `[dev]` extra |
| PRE-2.7 | MED-016 | `Dockerfile` | Lockfile-based installs |
| PRE-2.8 | MED-017 | `pyproject.toml` | MyPy strict_optional resolution |
| PRE-2.9 | MED-018 | `Dockerfile` | Docker service URLs |
| PRE-2.10 | MED-019 | `.github/workflows/ci.yml` | Codecov upload |
| PRE-2.11 | MED-032 | `.github/workflows/security-scan.yml` | Bandit `-c .bandit.yml` |
| PRE-2.12 | MED-033 | `conf/conda_environment_cpu.yaml` | CPU-only variant |

**Note**: R5-01 Phase A-SDK will require pinning `juniper-cascor-client>=<version>` via same-day follow-up PR per D-57. Coordinate with CI lockfile update workflow.

### Step PRE-3: Backend Services (Non-Adapter)

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PRE-3.1 | MED-034 | `src/backend/cascor_service_adapter.py` | TTL cache on `network` property (30s) |
| PRE-3.2 | MED-036 | `src/backend/service_backend.py` | KeyError guard in get_dataset |
| PRE-3.3 | MED-037 | `src/backend/data_adapter.py` | Lazy torch import |
| PRE-3.4 | MED-038 | `src/backend/data_adapter.py` | None guard in prepare_dataset_for_visualization |
| PRE-3.5 | MED-047 | `src/backend/training_monitor.py` | State dict replaces name-mangling |

**Note**: PRE-3.1 (TTL cache) is an independent performance optimization. It does NOT conflict with Phase C's `_control_stream_supervisor` work because the network property accesses a different code path.

### Step PRE-4: Frontend Logic (Non-WS)

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PRE-4.1 | HIGH-006 | `src/frontend/dashboard_manager.py` | Settings-based `_api_url` |
| PRE-4.2 | HIGH-007 | `src/frontend/components/network_visualizer.py` | Dynamic screenshot filename |
| PRE-4.3 | HIGH-011 | `src/main.py` | `importlib.metadata.version` |
| PRE-4.4 | HIGH-013 | `src/frontend/components/metrics_panel.py` | Shared `_add_phase_bg_bands` |
| PRE-4.5 | MED-002 | `src/communication/websocket_manager.py` | broadcast() + send_personal_message() dict copy |
| PRE-4.6 | MED-003 | `src/main.py` | Restrict HTTP CORS methods/headers |
| PRE-4.7 | MED-009 | `conf/app_config.yaml` | Update version to 0.4.0 |
| PRE-4.8 | MED-010 | `pyproject.toml` | Update header version |
| PRE-4.9 | MED-013 | `conf/app_config.yaml` | Fix CORS YAML list syntax (HTTP CORS, separate from WS origin) |
| PRE-4.10 | MED-020 | `src/main.py` | Remove duplicate cn_patience |
| PRE-4.11 | MED-023 | `src/middleware.py` | Content-length ValueError handling |
| PRE-4.12 | MED-028 | `src/frontend/dashboard_manager.py` | Remove time.sleep() |
| PRE-4.13 | MED-029 | `src/frontend/dashboard_manager.py` | Boolean dark mode toggle |
| PRE-4.14 | MED-030 | `src/frontend/components/about_panel.py` | Fix API.md broken link |

**Acceptance Criteria for Track PRE**:

- All Track PRE issues resolved
- Full test suite: 4,394+ passed, 0 failed
- Pre-commit hooks green

## 4. Track PAR: Parallel with R5-01

**Priority**: HIGH
**Dependencies**: None (can run while R5-01 phases are active)
**Blocks**: Release readiness
**Runs alongside**: R5-01 Phases 0-cascor through H

These are audit fixes that can proceed in parallel with R5-01 work without causing merge conflicts.

### Step PAR-1: Test Quality Fixes

**Note**: R5-01 Phase 0-cascor introduces `FakeCascorServerHarness` and contract tests. Test quality fixes should be applied BEFORE R5-01 Phase 0-cascor lands to ensure new tests don't inherit anti-patterns.

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PAR-1.1 | HIGH-016 | Multiple test files | Remove `contextlib.suppress(Exception)` around assertions (~18 sites) |
| PAR-1.2 | HIGH-018 | Multiple test files | Remove `hasattr` guards that skip test logic (~30 sites) |
| PAR-1.3 | HIGH-019 | `test_button_responsiveness.py` | Fix performance test no-ops |
| PAR-1.4 | MED-024 | `src/frontend/components/metrics_panel.py` | Remove `_create_candidate_pool_display` |
| PAR-1.5 | MED-025 | `src/frontend/components/metrics_panel.py` | Remove orphaned candidate callbacks |
| PAR-1.6 | MED-031 | `src/frontend/base_component.py` | Extract `create_empty_plot()` utility |
| PAR-1.7 | MED-048 | `src/tests/conftest.py` | Per-test isolation for session-scoped mock datasets |
| PAR-1.8 | MED-049 | `src/tests/conftest.py` | Direct singleton reset (no fragile hasattr) |
| PAR-1.9 | LOW-021 | `src/tests/conftest.py` | Remove deprecated event_loop fixture |
| PAR-1.10 | LOW-022 | `src/tests/regression/` | Verify regression tests use real code (already VERIFIED) |
| PAR-1.11 | HIGH-017 | `test_websocket_message_schema.py` | **Add pytest.fail guards**, then convert to `requires_server` marker -- full rework in Track EMB alignment with Phase 0-cascor |

### Step PAR-2: Observability & Logging

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PAR-2.1 | MED-004 | `src/observability.py` | Sentry traces_sample_rate configurable |
| PAR-2.2 | MED-005 | `src/observability.py` | Prometheus route-template labels |
| PAR-2.3 | MED-006 | `src/main.py`, `src/health.py` | Async probe_dependency |
| PAR-2.4 | MED-007 | `src/logger/logger.py` | Cache logger wrapper instances |
| PAR-2.5 | MED-008 | `src/logger/logger.py` | ColoredFormatter LogRecord save/restore |
| PAR-2.6 | MED-011 | `conf/logging_config.yaml` | File handler mode: a |
| PAR-2.7 | MED-012 | `conf/logging_config.yaml` | Production-safe default levels |
| PAR-2.8 | LOW-001-009 | `src/logger/logger.py`, `src/settings.py`, `src/config_manager.py`, `src/main.py` | Logger, settings, config cleanups (9 issues) |

**Note**: R5-01 introduces new Prometheus metrics (`canopy_rest_polling_bytes_per_sec`, `cascor_ws_seq_gap_detected_total`, etc.). Ensure that the route-template pattern from PAR-2.2 is applied consistently to these new metrics when they land.

### Step PAR-3: Low-Severity Cleanups

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| PAR-3.1 | LOW-008 | `src/main.py` | **MODIFY**: Align WS message size cap with R5-01 value (4096 bytes on /ws/training, 65536 on /ws/control) |
| PAR-3.2 | LOW-010 | `Dockerfile` | curl-based Docker health check (root only; `conf/Dockerfile` in POST track) |
| PAR-3.3 | LOW-011 | `.pre-commit-config.yaml` | Shellcheck severity warning |
| PAR-3.4 | LOW-012 | `.pre-commit-config.yaml` | Pre-commit autoupdate |
| PAR-3.5 | LOW-013 | `.codecov.yml` | Document after_n_builds |
| PAR-3.6 | LOW-014 | `pyproject.toml` | Black py314 target |
| PAR-3.7 | LOW-016 | `src/frontend/components/training_metrics.py` | Deprecation warning |
| PAR-3.8 | LOW-017 | `src/frontend/base_component.py` | Remove commented import |
| PAR-3.9 | LOW-018 | `src/frontend/components/network_visualizer.py` | Forward `_layout_type_sprint` params |
| PAR-3.10 | LOW-019 | `src/frontend/components/redis_panel.py` | Fix `_format_hit_rate` |
| PAR-3.11 | LOW-020 | `src/frontend/dashboard_manager.py` | Theme-aware header title |

**Acceptance Criteria for Track PAR**:

- All test quality, logging, and observability fixes applied
- Full test suite green
- Does not conflict with any in-progress R5-01 PR

## 5. Track EMB: R5-01 Phase-Embedded

**Priority**: HIGH
**Dependencies**: Specific R5-01 phase in progress
**Blocks**: R5-01 phase exit criteria
**Branches**: R5-01 phase branches (merged together)

These audit fixes are embedded AS PART OF R5-01 phase work. They must be coordinated with the R5-01 implementers to avoid duplicate effort.

### Step EMB-1: Phase 0-cascor Embedded Fixes

**R5-01 Phase**: Phase 0-cascor (2.0 days expected)
**Canopy work**: Minimal (cascor-primary phase)

| Task | Issue | File(s) | R5-01 Integration |
|------|-------|---------|-------------------|
| EMB-1.1 | HIGH-010 | `src/main.py` /ws endpoint | Phase 0-cascor restructures WS endpoints. The `finally` cleanup block fix is retained but the surrounding handler is rewritten. |
| EMB-1.2 | HIGH-017 | `test_websocket_message_schema.py` | Phase 0-cascor introduces `FakeCascorServerHarness` and `FakeCascorMessageSchema`. WebSocket schema tests become contract tests using the harness. |

### Step EMB-2: Phase B-pre-a Embedded Fixes (Read-Path Security)

**R5-01 Phase**: Phase B-pre-a (1.0 day)
**Canopy work**: Substantial (Origin, frame size, per-IP caps, audit log)

| Task | Issue | File(s) | R5-01 Integration |
|------|-------|---------|-------------------|
| EMB-2.1 | MED-001 | `src/communication/websocket_manager.py` | **MODIFIED**: Global max_connections becomes secondary to per-IP caps (5 default). Both enforced. |

**Note**: Track EMB-2 is primarily NEW R5-01 work (Origin validation, frame cap, audit logger) rather than audit remediation.

### Step EMB-3: Phase B Embedded Fixes (Frontend Wiring)

**R5-01 Phase**: Phase B (4.0 days, P0 win)
**Canopy work**: Major (drain callbacks, polling toggle, dead code removal)

| Task | Issue | File(s) | R5-01 Integration |
|------|-------|---------|-------------------|
| EMB-3.1 | MED-027 | `src/frontend/components/network_visualizer.py` | Phase B adds WS wire to network_visualizer.py. Callback restructure happens AS PART OF Phase B work. |

### Step EMB-4: Phase B-pre-b Embedded Fixes (Control-Path Security)

**R5-01 Phase**: Phase B-pre-b (1.5 days, parallel with B)
**Canopy work**: Substantial (CSRF, rate limit, HMAC)

No embedded audit fixes in this phase. R5-01 requirements are all NEW work.

### Step EMB-5: Phase C Embedded Fixes (Set_Params Adapter)

**R5-01 Phase**: Phase C (2.0 days)
**Canopy work**: Major (adapter refactor, hot/cold split)

| Task | Issue | File(s) | R5-01 Integration |
|------|-------|---------|-------------------|
| EMB-5.1 | MED-021 | `src/main.py` | Pydantic model for set_params, extended to route to adapter's hot/cold split |
| EMB-5.2 | MED-035 | `src/backend/cascor_service_adapter.py` | Relay loop exception handling aligned with `_control_stream_supervisor` |
| EMB-5.3 | MED-044 | `src/backend/training_monitor.py` | apply_params actual implementation |
| EMB-5.4 | MED-046 | `src/backend/service_backend.py`, `src/backend/cascor_service_adapter.py` | Public API for CascorServiceAdapter |

### Step EMB-6: Phase H Embedded Fixes (Regression Gate)

**R5-01 Phase**: Phase H (1.0 day)
**Canopy work**: Regression harness, CODEOWNERS

No embedded audit fixes, but HIGH-017 contract tests (from EMB-1.2) get final consolidation here.

## 6. Track POST: Post-R5-01 Deferred

**Priority**: MEDIUM
**Dependencies**: R5-01 Phase B in production + stable soak
**Blocks**: Post-release quality improvements
**Branches**: `chore/post-r5-*`

These audit fixes are deferred until R5-01 phases are complete and stable to prevent merge conflicts.

### Step POST-1: Architecture Refactors (After Phase B)

| Task | Issue | File(s) | Reason for Deferral |
|------|-------|---------|---------------------|
| POST-1.1 | HIGH-014 | `src/frontend/dashboard_manager.py` | Phase B rewrites large portions of dashboard_manager.py. Extracting into sub-modules now creates massive merge conflicts. Defer until post-Phase-B soak. |
| POST-1.2 | MED-026 | All frontend component files | Theme color rollout touches every component file. Phase B edits many of these. Defer until Phase B complete. |

### Step POST-2: conf/Dockerfile Alignment

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| POST-2.1 | HIGH-008 | `conf/Dockerfile` | Apply production defaults (DEMO_MODE=false, LOG_LEVEL=INFO) |
| POST-2.2 | MED-018 | `conf/Dockerfile` | Docker service URLs |
| POST-2.3 | LOW-010 | `conf/Dockerfile` | curl-based health check |

**Alternative**: If `conf/Dockerfile` is no longer in active use, document as deprecated and remove.

### Step POST-3: Low Severity Minor Completions

| Task | Issue | File(s) | Description |
|------|-------|---------|-------------|
| POST-3.1 | LOW-003 | `src/config_manager.py` | Simplify confusing ternary in `check_constants_category` |
| POST-3.2 | LOW-007 | `src/logger/logger.py` | Document FATAL_LEVEL=60 divergence from standard |

## 7. Execution Order

```text
Track PRE   [Now]                                                              [Release]
  │ ├─ PRE-1 (Critical security/concurrency)
  │ ├─ PRE-2 (CI/CD & config)
  │ ├─ PRE-3 (Backend services)
  │ └─ PRE-4 (Frontend logic)
  │
Track PAR   [Now]                                                              [Release]
  │ ├─ PAR-1 (Test quality) ◄── Must complete BEFORE R5-01 Phase 0-cascor
  │ ├─ PAR-2 (Observability & logging)
  │ └─ PAR-3 (Low severity cleanups)
  │
Track EMB   [R5-01 phases]                                                     [Release]
  │ ├─ EMB-1 (Phase 0-cascor)
  │ ├─ EMB-2 (Phase B-pre-a)
  │ ├─ EMB-3 (Phase B)
  │ ├─ EMB-4 (Phase B-pre-b)
  │ ├─ EMB-5 (Phase C)
  │ └─ EMB-6 (Phase H)
  │
Track POST  [After R5-01 Phase B stable in prod]                               [Post-release]
  │ ├─ POST-1 (Architecture refactors)
  │ ├─ POST-2 (conf/Dockerfile)
  │ └─ POST-3 (Minor LOW completions)
```

## 8. Phase Dependency Matrix

| Audit Phase | Independent? | Blocks R5-01? | Blocked By R5-01? |
|-------------|--------------|----------------|-------------------|
| Track PRE | Yes | No | No |
| Track PAR | Yes | No | No |
| Track EMB-1 | No | Phase 0-cascor exit | Phase 0-cascor start |
| Track EMB-2 | No | Phase B-pre-a exit | Phase B-pre-a start |
| Track EMB-3 | No | Phase B exit | Phase B start |
| Track EMB-4 | No | Phase B-pre-b exit | Phase B-pre-b start |
| Track EMB-5 | No | Phase C exit | Phase C start |
| Track EMB-6 | No | Phase H exit | Phase H start |
| Track POST-1 | No | None | Phase B stable in prod |
| Track POST-2 | Yes | No | No |
| Track POST-3 | Yes | No | No |

## 9. Testing Requirements

Every track must end with:

1. **Full test suite passes**
   - Track PRE/PAR target: 4,394+ passed, 0 failed (matches current audit remediation PR)
   - Track EMB targets: R5-01 phase-specific gates (see R5-01 Section 6.4 acceptance criteria)
   - Track POST target: 4,394+ passed, 0 failed post-R5-01 merge
2. **No new warnings introduced**
3. **Pre-commit hooks pass**
4. **CI pipeline green**
5. **R5-01 contract tests (where applicable) green**

## 10. Completion Status (as of 2026-04-12)

| Track/Phase | Status | Notes |
|-------------|--------|-------|
| Track PRE | PARTIAL (via PR #146) | 25 of 25+ issues addressed in PR #146; some gaps remain |
| Track PAR | PARTIAL (via PR #146) | Test quality fixes (HIGH-016/018/019) complete; HIGH-017 partial |
| Track EMB-1 | NOT STARTED | Blocked by R5-01 Phase 0-cascor start |
| Track EMB-2 | NOT STARTED | Blocked by R5-01 Phase B-pre-a start |
| Track EMB-3 | NOT STARTED | Blocked by R5-01 Phase B start |
| Track EMB-4 | NOT STARTED | Blocked by R5-01 Phase B-pre-b start |
| Track EMB-5 | NOT STARTED | Blocked by R5-01 Phase C start |
| Track EMB-6 | NOT STARTED | Blocked by R5-01 Phase H start |
| Track POST | NOT STARTED | Blocked by R5-01 Phase B production soak |

**PR #146** (`fix/code-review-audit-remediation`) completed substantial Track PRE and Track PAR work:

- 25 code review gaps remediated across 29 files
- Full suite: 4,394 passed, 94 skipped, 0 failed

**Deferred from PR #146**:

- HIGH-014: Deferred to Track POST-1
- HIGH-005: SUPERSEDED (no action needed; R5-01 Phase B provides canonical fix)
- MED-026: Deferred to Track POST-1
- HIGH-008 (conf/Dockerfile partial): Moved to Track POST-2
- MED-018 (conf/Dockerfile partial): Moved to Track POST-2
- LOW-010 (conf/Dockerfile partial): Moved to Track POST-2

## 11. Critical Path Notes

### Track PAR-1 Must Precede R5-01 Phase 0-cascor

**Why**: Phase 0-cascor introduces `FakeCascorServerHarness` and contract tests. These will use pytest infrastructure (fixtures, markers, helpers). If test quality anti-patterns (`contextlib.suppress`, `hasattr` guards) are not resolved BEFORE Phase 0-cascor lands, the new contract tests may inherit these patterns by copy-paste.

**Rule**: Block R5-01 Phase 0-cascor merge until HIGH-016/018/019 are resolved (already in PR #146, but confirm merged).

### R5-01 Phase B Must Precede Track POST-1

**Why**: `dashboard_manager.py` (HIGH-014) will be substantially rewritten in Phase B. Extracting into sub-modules now would create merge conflicts so large that the extraction becomes infeasible. Wait for Phase B to stabilize in production.

**Rule**: POST-1.1 extraction PR cannot start until R5-01 Phase B flag-flip has >=7 days of production soak with no page alerts.

### conf/Dockerfile Decision Needed Before Track POST-2

**Why**: If `conf/Dockerfile` is deprecated and unused, POST-2 work should be replaced with a deletion PR. If still in active use, the three partial-fix completions are needed.

**Rule**: Before starting POST-2, confirm with ops whether `conf/Dockerfile` is still in active use.

## 12. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Track PAR-1 not completed before R5-01 Phase 0-cascor | New contract tests inherit anti-patterns | CI gate: no contract test PRs can merge until HIGH-016/018/019 marked complete in audit tracking |
| Track EMB merge conflicts with R5-01 PRs | Wasted work, rework needed | Coordinate via shared roadmap; no Track EMB work without R5-01 phase owner handoff |
| Track POST-1 delayed by Phase B instability | HIGH-014 lingers indefinitely | Accept as ongoing technical debt; revisit quarterly |
| R5-01 Phase B changes test count (4,394 → 4,500+) | Audit test count claims become stale | Update audit numbers post-R5-01; tests should remain 0 failures |

---

*Document generated: 2026-04-12*
*Supersedes: CODE_REVIEW_PLAN_2026-04-04.md (for planning decisions)*
*Source of truth: R5-01_canonical_development_plan.md*
*Companion: CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md, CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md, CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md*
