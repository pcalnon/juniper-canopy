# Juniper Canopy -- Code Review Development Roadmap (R5-01 Aligned)

**Date**: 2026-04-12
**Version**: 0.4.0
**Source of Truth**: [R5-01 Canonical Development Plan](../../juniper-ml/notes/interface_proposals/R5-01_canonical_development_plan.md)
**Supersedes**: [CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md](CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md)

**Companion Documents**:

- [CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md](CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md)
- [CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md](CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md)
- [CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md](CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md)

---

## Executive Summary

This roadmap reorganizes the original 5-phase code review remediation timeline to coordinate with the **R5-01 Canonical Development Plan** -- the authoritative source of truth for the juniper-canopy <-> juniper-cascor interface. R5-01 defines 11 phases of WebSocket, security, and architectural work that will substantially modify canopy's backend adapter, frontend dashboard, and test infrastructure.

The prior roadmap assumed all audit issues could be remediated independently. This assumption is **invalid** for 10 of 99+ issues that interact directly with R5-01's scope. This document provides a revised roadmap with track-based sequencing (PRE, PAR, EMB, POST) that prevents merge conflicts and avoids duplicate work.

### Key Changes vs Original Roadmap

| Change | Description | Impact |
|--------|-------------|--------|
| **Track structure replaces Phase structure** | 4 tracks (PRE/PAR/EMB/POST) instead of 5 phases (0-5) | Enables parallel execution with R5-01 |
| **HIGH-005 superseded** | Async HTTP migration replaced by R5-01 Phase B WebSocket bridge | No further canopy-side work needed |
| **HIGH-014 deferred** | DashboardManager extraction waits for R5-01 Phase B stability | Avoids massive merge conflict |
| **MED-026 deferred** | ThemeColors rollout waits for Phase B to complete | Avoids threading rollout through Phase B edits |
| **7 issues coordinated** | HIGH-010, HIGH-017, MED-021/027/035/044/046 | Align with specific R5-01 phases |
| **1 issue modified** | MED-001 defers to R5-01 per-IP caps | Global limit becomes secondary |
| **20 new requirements added** | R5-01-NEW-001 through R5-01-NEW-020 | Tracked as forward work, not audit gaps |

## 1. Roadmap Overview

```text
Track PRE ──── Pre-R5-01 Independent Fixes ───────────── [Release Blocker]
                    │
                    │  (No R5-01 dependency)
                    │
Track PAR ──── Parallel with R5-01 ──────────────────── [Release Blocker]
                    │
                    │  (Runs alongside R5-01 phases)
                    │
R5-01 Phases ──── Canonical Interface Implementation ─── [Release Enabler]
   │                │
   ├── Phase 0-cascor ── Seq, replay, resume (2.0d)
   ├── Phase A-SDK ── set_params to PyPI (1.0d, parallel)
   ├── Phase B-pre-a ── Read-path security (1.0d)
   ├── Phase B ── Frontend wiring, polling eliminated (4.0d) [P0 WIN]
   ├── Phase B-pre-b ── Control-path security (1.5d, parallel)
   ├── Phase C ── set_params adapter (2.0d)
   ├── Phase D ── Control buttons (1.0d)
   ├── Phase E ── Backpressure (1.0d, CONDITIONAL)
   ├── Phase F ── Heartbeat (0.5d)
   ├── Phase G ── Cascor integration tests (0.5d)
   └── Phase H ── Regression gate + CODEOWNERS (1.0d)
                    │
Track EMB ──── R5-01 Phase-Embedded Fixes ────────────── [Merged with R5-01]
                    │
                    │  (Applied AS PART OF R5-01 phase PRs)
                    │
Track POST ──── Post-R5-01 Deferred ──────────────────── [Post-Release Quality]
                    │
                    │  (Waits for R5-01 Phase B stable in production)
                    │
                    ▼
                 [Release]
```

## 2. Track PRE: Pre-R5-01 Independent Fixes

**Priority**: IMMEDIATE
**Dependencies**: None
**Blocks**: Release
**Status as of 2026-04-12**: **SUBSTANTIALLY COMPLETE** via PR #146

### Goals

Fix all release-blocking security, concurrency, CI/CD, and backend service issues that are independent of R5-01. These fixes have no interaction with the canopy-cascor interface and can proceed without any R5-01 coordination.

### Completed via PR #146

- [x] **CRIT-001**: Path traversal sanitization
- [x] **CRIT-002**: contextvars migration
- [x] **CRIT-003**: Lockfile extras
- [x] **HIGH-001/002/003**: Security fixes (timing, errors, rate limiter)
- [x] **HIGH-004**: threading.Event fix
- [x] **HIGH-006**: Settings-based _api_url
- [x] **HIGH-007**: Dynamic screenshot filename
- [x] **HIGH-008/009/012**: CI/CD fixes (Docker, bandit, permissions)
- [x] **HIGH-011**: importlib.metadata version
- [x] **HIGH-013**: Shared phase band method
- [x] **HIGH-015**: TrainingStateMachine locks (including getters)
- [x] **MED-003**: HTTP CORS restrictions
- [x] **MED-034/037/038**: Backend service fixes
- [x] **MED-039/040/041/042/043**: Cassandra + Redis fixes
- [x] **MED-044/046/047**: Partial -- will be completed in Track EMB-5
- [x] **Other MED and LOW issues**: See PR #146 commit message

### Deferred from PR #146 to Other Tracks

| Issue | Moved To | Reason |
|-------|----------|--------|
| HIGH-005 | **SUPERSEDED** | R5-01 Phase B provides canonical fix |
| HIGH-014 | Track POST-1 | Conflicts with Phase B edits |
| MED-026 | Track POST-1 | Component files edited in Phase B |
| HIGH-008 conf/Dockerfile | Track POST-2 | Secondary Dockerfile needs separate review |
| MED-018 conf/Dockerfile | Track POST-2 | Secondary Dockerfile needs separate review |
| LOW-010 conf/Dockerfile | Track POST-2 | Secondary Dockerfile needs separate review |

### Remaining Track PRE Work

All Track PRE work is complete as of 2026-04-12 PR #146 merge.

## 3. Track PAR: Parallel with R5-01

**Priority**: HIGH
**Dependencies**: None (runs alongside R5-01)
**Blocks**: Release
**Status as of 2026-04-12**: **SUBSTANTIALLY COMPLETE** via PR #146

### Goals

Fix test quality, observability, and low-severity issues in parallel with R5-01 phases. Track PAR-1 (test quality) MUST complete before R5-01 Phase 0-cascor starts to prevent contamination of new contract tests.

### Completed via PR #146

- [x] **HIGH-016**: Removed contextlib.suppress from test assertions
- [x] **HIGH-018**: Removed hasattr guards from test bodies
- [x] **HIGH-019**: Fixed performance test no-ops (3 of 5 tests real)
- [x] **MED-024/025**: Dead code and orphaned callback removal
- [x] **MED-031**: Shared create_empty_plot utility
- [x] **MED-048/049**: conftest.py test infrastructure fixes
- [x] **LOW-021**: Removed deprecated event_loop fixture
- [x] **LOW-022**: Regression tests verified to use real code
- [x] **MED-004 through MED-012**: Observability and logging fixes
- [x] **LOW-001 through LOW-009**: Minor logger/settings/config cleanups
- [x] **LOW-011/012/013/014**: Pre-commit and config cleanups
- [x] **LOW-016/017/018/019/020**: Frontend cleanups

### Partial / Coordinated

- [~] **HIGH-017**: Partial (pytest.fail guards added); full rework to contract tests happens in Track EMB-1 with Phase 0-cascor
- [ ] **LOW-008**: **MODIFY** to align with R5-01 WS frame size caps (4096 bytes on /ws/training, 65536 on /ws/control)

### Remaining Track PAR Work

| Task | Issue | Priority | Target |
|------|-------|----------|--------|
| PAR-3.1 | LOW-008 MODIFY | LOW | Before R5-01 Phase B-pre-a |

Track PAR is otherwise complete.

## 4. R5-01 Canonical Phase Execution

This section summarizes the 11 R5-01 phases and their canopy impact. See [R5-01 Canonical Development Plan](../../juniper-ml/notes/interface_proposals/R5-01_canonical_development_plan.md) for full detail.

### Phase 0-cascor: Seq, Replay, Resume (2.0 days)

**Status**: NOT STARTED
**Primary Owner**: juniper-cascor
**Canopy Impact**: Minimal (cascor-primary)

**Canopy work**:

- Update `cascor_service_adapter.py` to parse new envelope fields (`seq`, `emitted_at_monotonic`, `server_instance_id`, `replay_buffer_capacity`)
- Update `websocket_message_schema` contract tests (embedded fix EMB-1.2 for HIGH-017)
- Add `CascorServerFrame` Pydantic model with `extra="allow"`

**Audit fixes embedded**:

- EMB-1.1: HIGH-010 (/ws endpoint restructure)
- EMB-1.2: HIGH-017 (schema tests become contract tests)

**Acceptance Gates** (blocking for P0):

- 26+ unit + 5 integration + 3 chaos + load tests green
- `cascor_ws_seq_gap_detected_total==0` during 72h soak
- `broadcast_from_thread_errors_total==0` during soak

### Phase A-SDK: set_params to PyPI (1.0 day, parallel)

**Status**: NOT STARTED
**Primary Owner**: juniper-cascor-client
**Canopy Impact**: Import new version

**Canopy work**:

- Bump pin: `juniper-cascor-client>=<version>` (same-day follow-up PR per D-57)
- No code changes in canopy (just dependency pin)

**Audit fixes embedded**: None

### Phase B-pre-a: Read-Path Security (1.0 day)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: **Substantial** (Origin, frame size, per-IP caps, audit log)

**Canopy work**:

- Add `src/backend/ws_security.py` (NEW): Origin validation helper
- Add `src/backend/audit_log.py` (NEW): JSON logger with CRLF escape
- Add `ws_allowed_origins`, `ws_max_connections_per_ip`, `ws_idle_timeout_seconds`, `audit_log_*` settings
- Wire `/ws/training` route: Origin, frame size cap, per-IP cap, 120s idle timeout
- Add `_pending_connections: set[WebSocket]` for two-phase registration

**Audit fixes embedded**:

- EMB-2.1: MED-001 (max_connections becomes secondary to per-IP caps)

**Acceptance Gates**:

- CSWSH probe from `http://evil.example.com` rejected
- 65KB frame returns close 1009
- 6th same-IP connection returns close 1013
- Empty allowlist rejects all (fail-closed)
- 24-hour soak with zero user lockout

### Phase B: Frontend Wiring + Polling Elimination (4.0 days) **P0 WIN**

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: **Major** (dashboard_manager.py refactor, new JS bridge, connection indicator)

**Canopy work**:

- Add `src/frontend/assets/ws_dash_bridge.js` (NEW, ~200 LOC)
- Add `src/frontend/assets/ws_latency.js` (NEW, ~50 LOC)
- Add `src/frontend/components/connection_indicator.py` (NEW)
- Edit `src/frontend/dashboard_manager.py`:
  - Delete lines 1490-1526 (dead raw-WS callback, GAP-WS-03)
  - Add 5 `dcc.Store` instances (metrics/state/topology/cascade_add/candidate_progress)
  - Refactor `_update_metrics_store_handler` (lines 2388-2421)
  - Apply polling-toggle pattern to all poll handlers
  - Delete `window._juniper_ws_*` globals
- Edit `src/frontend/components/metrics_panel.py`: clientside `Plotly.extendTraces`, `uirevision`
- Edit `src/frontend/components/network_visualizer.py`: minimum WS wire for topology/cascade_add
- Add `POST /api/ws_latency`, `POST /api/ws_browser_errors` endpoints
- Add feature flags: `enable_browser_ws_bridge`, `disable_ws_bridge`, `enable_raf_coalescer`, `enable_ws_latency_beacon`

**Audit fixes embedded**:

- EMB-3.1: MED-027 (NetworkVisualizer callback restructure as part of Phase B)

**Acceptance Gates** (P0 Win):

- `canopy_rest_polling_bytes_per_sec` >=90% lower than baseline in staging (1h)
- Browser memory p95 <=500 MB
- Drain callback gen advancing
- 72h staging with flag on, no page alerts

### Phase B-pre-b: Control-Path Security (1.5 days, parallel with B)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: **Substantial** (CSRF, rate limit, HMAC)

**Canopy work**:

- Add `GET /api/csrf` endpoint
- Extend SessionMiddleware (if absent, +0.5d budget)
- Wire `/ws/control` route: CSRF first-frame auth (5s timeout)
- Single-bucket leaky bucket rate limiter (10 cmd/s, configurable)
- Per-origin handshake cooldown (10 rejections in 60s → 5-min IP block)
- HMAC CSRF token for adapter: `HMAC(api_key, "adapter-ws").hexdigest()`
- Add settings: `ws_security_enabled` (CI-enforced True in prod), `ws_rate_limit_*`, `disable_ws_control_endpoint`

**Audit fixes embedded**: None (all R5-01 new work)

**Acceptance Gates**:

- `WSOriginRejection` alert test-fired
- CSRF required for browser `/ws/control`
- HMAC required for adapter `/ws/control`
- Rate limit soft response (not close)
- B-pre-b in production >=48h before Phase D merge

### Phase C: set_params Adapter with REST Fallback (2.0 days)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: **Major** (adapter refactor, hot/cold split)

**Canopy work**:

- Edit `src/backend/cascor_service_adapter.py`:
  - Add `_HOT_CASCOR_PARAMS: frozenset[str]` (11 params)
  - Add `_COLD_CASCOR_PARAMS: frozenset[str]` (2 params)
  - Add `apply_params(params)` method with hot/cold split
  - Add `_control_stream_supervisor` background task (backoff [1,2,5,10,30]s)
  - Add bounded correlation map (max 256, raises `JuniperCascorOverloadError`)
  - Add `CascorServerFrame` Pydantic model (`extra="allow"`)
  - Add `_assign_command_id()` helper
- Add `use_websocket_set_params` feature flag
- Add `ws_set_params_timeout` setting (default 1.0s)
- Edit `src/backend/service_backend.py`: Use new public API

**Audit fixes embedded**:

- EMB-5.1: MED-021 (Pydantic model for set_params -- extended to adapter's hot/cold split)
- EMB-5.2: MED-035 (Relay loop exception handling aligned with `_control_stream_supervisor`)
- EMB-5.3: MED-044 (TrainingMonitor.apply_params actual implementation)
- EMB-5.4: MED-046 (Public API for CascorServiceAdapter)

**Acceptance Gates**:

- Flag off: `transport="rest"` has data; `transport="ws"` empty
- Slider drag within 1s; kill cascor → REST fallback within 2s
- >=7 days production WS code path data before flag flip
- Zero correlation-map leaks
- Zero orphaned commands during canary

### Phase D: Control Buttons (1.0 day)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: Moderate (training_controls.py edit, WS commands)

**Canopy work**:

- Edit `src/frontend/components/training_controls.py`: clientside callback for buttons, WS send when connected, REST POST fallback
- Wire start/stop/pause/resume/reset via WS `/ws/control`
- Add `enable_ws_control_buttons` feature flag

**Audit fixes embedded**: None

**Acceptance Gates**:

- `test_csrf_required_for_websocket_start` passes
- Start with WS → state within 10s
- Kill cascor → REST succeeds
- 24h soak zero orphaned commands
- REST endpoints still receive traffic (fallback paths alive)

### Phase E: Backpressure (1.0 day, CONDITIONAL)

**Status**: NOT STARTED (may not execute if telemetry insufficient)
**Primary Owner**: juniper-canopy
**Canopy Impact**: Conditional

**Canopy work** (conditional):

- Per-client `_ClientState` with `pump_task` + bounded `send_queue` (256)
- Async queue per client (not serial fan-out)
- Policy dispatch (drop_oldest_progress_only default)

**Audit fixes embedded**: None

### Phase F: Heartbeat (0.5 days)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: Minor

**Canopy work**:

- Server emits `{type: "ping", ts: float}` every 30s
- Client replies `{type: "pong"}` within 5s
- Dead connection → close 1006

### Phase G: Cascor Integration Tests (0.5 days)

**Status**: NOT STARTED
**Primary Owner**: juniper-cascor + juniper-canopy
**Canopy Impact**: Minor (test coordination)

### Phase H: Regression Gate + CODEOWNERS (1.0 day)

**Status**: NOT STARTED
**Primary Owner**: juniper-canopy
**Canopy Impact**: Test infrastructure

**Canopy work**:

- Add normalize_metric regression gate
- Add CODEOWNERS enforcement
- Consumer audit doc
- Pre-commit hooks for lint rules

**Audit fixes embedded**:

- EMB-6.1: HIGH-017 final consolidation

## 5. Track POST: Post-R5-01 Deferred

**Priority**: MEDIUM
**Dependencies**: R5-01 Phase B stable in production
**Blocks**: Post-release quality improvements

### Step POST-1: Architecture Refactors (After Phase B Stable)

| Task | Issue | Target | Effort |
|------|-------|--------|--------|
| POST-1.1 | HIGH-014 | Extract DashboardManager sub-modules | High (multi-day) |
| POST-1.2 | MED-026 | Wire ThemeColors into all component files | High (multi-day) |

**Prerequisite**: Phase B flag-flipped in production with >=7 days soak and zero page alerts.

### Step POST-2: conf/Dockerfile Alignment

**Prerequisite**: Ops decision on whether `conf/Dockerfile` is still active.

| Task | Issue | Action |
|------|-------|--------|
| POST-2.1 | HIGH-008 | Apply production defaults to conf/Dockerfile (or remove file) |
| POST-2.2 | MED-018 | Docker service URLs (or remove file) |
| POST-2.3 | LOW-010 | curl-based health check (or remove file) |

### Step POST-3: Minor Completions

| Task | Issue | Action |
|------|-------|--------|
| POST-3.1 | LOW-003 | Simplify confusing ternary in config_manager |
| POST-3.2 | LOW-007 | Document FATAL_LEVEL=60 divergence |

## 6. Timeline & Dependencies

### Week 1 (2026-04-12 to 2026-04-19)

**Now**: Audit work substantially complete (PR #146).

**Ongoing**:

- Review and merge PR #144 (audit plan document)
- Review and merge PR #146 (audit remediation)
- R5-01 Phase 0-cascor planning / implementation kickoff

### Week 2 (2026-04-20 to 2026-04-26)

**R5-01 Phase 0-cascor** execution (2.0 days)
**R5-01 Phase A-SDK** execution (1.0 day, parallel)
**Track EMB-1** embedded in Phase 0-cascor PRs

### Week 3 (2026-04-27 to 2026-05-03)

**R5-01 Phase 0-cascor** 72h soak (blocking gate)
**R5-01 Phase B-pre-a** execution (1.0 day)
**Track EMB-2** embedded in Phase B-pre-a PRs

### Week 4-5 (2026-05-04 to 2026-05-17)

**R5-01 Phase B** execution (4.0 days) **[P0 WIN]**
**R5-01 Phase B-pre-b** execution (1.5 days, parallel)
**Track EMB-3** embedded in Phase B PRs
**Track EMB-4** embedded in Phase B-pre-b PRs

### Week 6+ (post 2026-05-18)

**R5-01 Phase B** 72h production soak → flag flip (P0 win achieved)
**R5-01 Phase C** execution (2.0 days)
**Track EMB-5** embedded in Phase C PRs
**R5-01 Phase D** execution (1.0 day) after B-pre-b 48h prod soak
**R5-01 Phase E/F/G/H** as per R5-01 sequencing

### Week 12+ (after Phase B stable in prod for >=7 days)

**Track POST-1** (HIGH-014, MED-026)
**Track POST-2** (conf/Dockerfile)
**Track POST-3** (LOW-003, LOW-007)

## 7. Resource Allocation

| Role | Track PRE | Track PAR | R5-01 Phases | Track POST |
|------|-----------|-----------|--------------|------------|
| Primary dev | Complete (PR #146) | Complete (PR #146) | Phase B leads | POST-1 leads |
| Code review | Complete (PR #146) | Complete (PR #146) | Cross-project | Single reviewer OK |
| QA | Test suite validation | Test suite validation | R5-01 acceptance gates | Test suite validation |
| Ops | None | None | Phase B soak monitoring | None |

## 8. Metrics & Monitoring

### Pre-R5-01 Metrics (Track PRE/PAR)

- Test pass count: 4,394 passed, 94 skipped, 0 failed (as of PR #146)
- Audit gap count: 34 identified, 25 fixed, 9 deferred (post-PR #146)
- Code review completion rate: ~74% (25/34 gaps)

### R5-01 Metrics (tracked by R5-01 plan)

- `canopy_rest_polling_bytes_per_sec` (P0 win metric)
- `cascor_ws_seq_gap_detected_total` (0-cascor gate)
- `broadcast_from_thread_errors_total` (0-cascor gate)
- `canopy_ws_origin_rejected_total` (B-pre-a health)
- `canopy_ws_browser_heap_mb` (Phase B soak)
- `canopy_ws_orphaned_commands_total` (Phase C/D health)

### Post-R5-01 Metrics (Track POST)

- DashboardManager LOC (HIGH-014 target: <2,000; current: 3,007)
- Hardcoded color count (MED-026 target: 0; current: ~169)
- conf/Dockerfile compliance with root Dockerfile

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| R5-01 Phase 0-cascor delay cascades to all downstream phases | Medium | High | Track PRE/PAR work already unblocks release; R5-01 delays do not block audit-level release |
| Track EMB coordination failures (duplicate work) | Medium | Medium | Shared roadmap; explicit handoff from audit PR owners to R5-01 phase owners |
| POST-1 HIGH-014 extraction becomes infeasible after Phase B | Low | Medium | Accept as ongoing technical debt; revisit quarterly |
| R5-01 Phase B kill switch needed post-flag-flip | Low | High (P0) | Kill-switch MTTR <=5 min required per D-53; R5-01 has kill switches |
| `conf/Dockerfile` ambiguity blocks POST-2 | Low | Low | Ops decision required; fallback is deletion |

## 10. Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Supersede HIGH-005 | R5-01 Phase B provides canonical fix (WS bridge eliminates polling) | 2026-04-12 |
| Defer HIGH-014 to Track POST-1 | Phase B rewrites large portions of dashboard_manager.py; extraction conflicts | 2026-04-12 |
| Defer MED-026 to Track POST-1 | ThemeColors rollout touches all component files; Phase B also edits them | 2026-04-12 |
| Modify MED-001 interpretation | R5-01 per-IP caps supersede global max_connections as primary defense | 2026-04-12 |
| Coordinate HIGH-010 with Phase 0-cascor | WebSocket endpoints substantially rewritten in Phase 0-cascor | 2026-04-12 |
| Coordinate HIGH-017 with Phase 0-cascor + H | Schema tests become contract tests via FakeCascorServerHarness | 2026-04-12 |
| Coordinate MED-021/044/046 with Phase C | set_params adapter refactor happens in Phase C | 2026-04-12 |
| Coordinate MED-035 with Phase C | Relay loop rewritten in Phase C `_control_stream_supervisor` | 2026-04-12 |
| Coordinate MED-027 with Phase B | network_visualizer.py edited for WS wire in Phase B | 2026-04-12 |

## 11. Completion Status (as of 2026-04-12)

| Track | Tasks | Completed | Remaining | % Complete |
|-------|-------|-----------|-----------|------------|
| Track PRE | ~40 | ~38 | ~2 (conf/Dockerfile in POST-2) | ~95% |
| Track PAR | ~30 | ~28 | ~2 (LOW-008 modify, HIGH-017 full rework) | ~93% |
| Track EMB | ~7 coordinated | 0 | 7 (blocked by R5-01 phases) | 0% |
| Track POST | ~7 | 0 | 7 (blocked by R5-01 Phase B) | 0% |
| **Total** | **~84** | **~66** | **~18** | **~79%** |

**Overall Status**: Track PRE and Track PAR are substantially complete via PR #146. Track EMB and Track POST are blocked by R5-01 sequencing, which is expected and correct.

## 12. Next Steps

1. **Immediate** (this week):
   - Merge PR #144 (audit plan document, canonical-aligned versions to be added)
   - Merge PR #146 (audit remediation, 25 gaps fixed)
   - Kick off R5-01 Phase 0-cascor planning

2. **Short-term** (next 2 weeks):
   - R5-01 Phase 0-cascor execution with Track EMB-1 embedded fixes
   - R5-01 Phase A-SDK parallel execution

3. **Medium-term** (next 4-6 weeks):
   - R5-01 Phases B-pre-a, B, B-pre-b, C execution
   - Track EMB-2 through EMB-5 embedded fixes

4. **Long-term** (post R5-01 Phase B production stable):
   - Track POST-1 DashboardManager extraction
   - Track POST-1 ThemeColors rollout
   - Track POST-2 conf/Dockerfile decision + cleanup
   - Track POST-3 LOW completions

---

*Document generated: 2026-04-12*
*Supersedes: CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md*
*Source of truth: R5-01_canonical_development_plan.md*
*Companion: CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md, CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md, CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md*
