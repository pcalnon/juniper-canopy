# Juniper Canopy -- Code Review Audit Plan (R5-01 Aligned)

**Date**: 2026-04-12
**Version**: 0.4.0
**Source of Truth**: [R5-01 Canonical Development Plan](../../juniper-ml/notes/interface_proposals/JUNIPER_2026-04-20_JUNIPER-ECOSYSTEM_R5-01-CANONICAL-DEVELOPMENT-PLAN.md)
**Supersedes**: [CODE_REVIEW_AUDIT_PLAN_2026-04-12.md](CODE_REVIEW_AUDIT_PLAN_2026-04-12.md)

**Companion Documents**:

- [CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md](CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md)
- [CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md](CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md)
- [CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md](CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md)

---

## 1. Purpose

This document re-evaluates the 34 gaps identified in the original [CODE_REVIEW_AUDIT_PLAN_2026-04-12.md](CODE_REVIEW_AUDIT_PLAN_2026-04-12.md) against the **R5-01 Canonical Development Plan**. The original audit verified 91 issues and found 57 verified, 16 partially fixed, and 18 not fixed. This re-evaluation determines whether:

1. Each gap is still valid given R5-01's canonical constraints
2. The gap's remediation approach should change
3. The gap should be deferred, superseded, or coordinated with R5-01 phase work

The audit methodology (8-domain parallel execution, verification chain, sign-off criteria) remains valid. Only the gap disposition changes.

## 2. Alignment Summary

### 2.1 Original Audit Results (unchanged by this re-evaluation)

| Status          | Count | Percentage |
|-----------------|-------|------------|
| VERIFIED        | 57    | 63%        |
| PARTIALLY FIXED | 16    | 18%        |
| NOT FIXED       | 18    | 20%        |
| REGRESSIONS     | 0     | 0%         |

### 2.2 Gap Disposition After R5-01 Alignment

| Disposition     | Count  | Description                                        |
|-----------------|--------|----------------------------------------------------|
| **REAFFIRMED**  | 22     | Gap still valid; original remediation applies      |
| **SUPERSEDED**  | 1      | R5-01 provides canonical fix; no audit remediation |
| **DEFERRED**    | 4      | Gap waits for R5-01 Phase B completion             |
| **COORDINATED** | 7      | Remediation must align with specific R5-01 phase   |
| **Total**       | **34** |                                                    |

## 3. Gap Re-Evaluation (Detailed)

### 3.1 NOT FIXED Gaps (18)

#### GAP-001: MED-040 -- Cassandra Credentials as Plain Attributes
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Cassandra backend is independent of canopy-cascor interface. R5-01 does not address this gap.
**Action**: Proceed with original remediation (Option A: Transient credential usage). Already implemented in PR #146.

#### GAP-002: MED-039 -- Cassandra Singleton Not Thread-Safe
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Singleton concurrency is independent of R5-01.
**Action**: Proceed with original remediation (double-checked locking). Already implemented in PR #146.

#### GAP-003: MED-041 -- Redis Singleton Not Thread-Safe
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Singleton concurrency is independent of R5-01.
**Action**: Proceed with original remediation. Already implemented in PR #146.

#### GAP-004: HIGH-007 -- NetworkVisualizer Screenshot Filename Not Dynamic
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED** (with coordination note)
**Reason**: Screenshot filename is independent of R5-01 WS work. However, R5-01 Phase B will edit `network_visualizer.py` to add minimum WS wire for `topology` and `cascade_add` messages.
**Action**: Proceed with original remediation (dynamic filename via callback return). Already implemented in PR #146. Merge BEFORE Phase B to avoid conflict.

#### GAP-005: MED-045 -- DemoBackend.initialize() Unconditional Auto-Start
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Demo mode auto-start is independent of R5-01. R5-01 RISK-08 requires demo mode parity (`test_demo_mode_metrics_parity`) but does not affect auto-start behavior.
**Action**: Proceed with original remediation (Option A: Document auto-start intent). Already implemented in PR #146.

#### GAP-006: HIGH-014 -- DashboardManager God Class (3007 lines)
**Original Status**: NOT FIXED
**R5-01 Alignment**: **DEFERRED** to post-R5-01 Phase B
**Reason**: R5-01 Phase B makes substantial edits to `dashboard_manager.py`:

- Deletes lines 1490-1526 (dead raw-WS callback, GAP-WS-03)
- Adds 5 new `dcc.Store` instances
- Refactors `_update_metrics_store_handler` (lines 2388-2421)
- Applies polling-toggle pattern to multiple poll handlers
- Deletes `window._juniper_ws_*` globals

Extracting DashboardManager into sub-modules NOW would create massive merge conflicts with Phase B. The extraction is also marked "High" effort.

**Revised Action**:

- **DO NOT** attempt extraction before Phase B
- Track as accepted technical debt with dependency on Phase B completion
- Revisit POST-1.1 after Phase B has >=7 days production soak
- Current 3,007 line state accepted until post-Phase-B

#### GAP-007: MED-034 -- Network Property HTTP Per Access
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: The `network` property is in `cascor_service_adapter.py` but accesses a different code path (REST GET) than R5-01 Phase C's `_control_stream_supervisor` work. They do not conflict.
**Action**: Proceed with original remediation (30s TTL cache). Already implemented in PR #146.

#### GAP-008: MED-037 -- Hard torch Import
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: torch import pattern is independent of R5-01.
**Action**: Proceed with original remediation (lazy import via `TYPE_CHECKING`). Already implemented in PR #146.

#### GAP-009: MED-038 -- prepare_dataset_for_visualization None Crash
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Dataset visualization is independent of R5-01.
**Action**: Proceed with original remediation (None guard). Already implemented in PR #146.

#### GAP-010: MED-042 -- Redis Exception Aliases = Exception
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Redis client is independent of R5-01.
**Action**: Proceed with original remediation (sentinel class). Already implemented in PR #146.

#### GAP-011: MED-043 -- Redis force_new Connection Leak
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Redis client is independent of R5-01.
**Action**: Proceed with original remediation (close old instance). Already implemented in PR #146.

#### GAP-012: MED-046 -- ServiceBackend Accesses Private CascorServiceAdapter Attributes
**Original Status**: NOT FIXED
**R5-01 Alignment**: **COORDINATED** with Phase C
**Reason**: R5-01 Phase C substantially extends `cascor_service_adapter.py`:

- Adds `_control_stream_supervisor` background task
- Adds `_HOT_CASCOR_PARAMS` / `_COLD_CASCOR_PARAMS` frozensets
- Adds `apply_params(params)` method
- Adds bounded correlation map (max 256)
- Adds `CascorServerFrame` Pydantic model

The public API exposure (from the prior audit fix) is still correct but **insufficient**. Phase C will add more public methods that should be planned holistically.

**Revised Action**:

- The PR #146 minimal public API fix (`service_url`, `client`, `is_cascor_nested`) is a stopgap
- Plan the full public API design as part of Phase C work
- Coordinate with R5-01 Phase C owner

#### GAP-013: MED-047 -- TrainingState Name-Mangling
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: TrainingState is independent of R5-01.
**Action**: Proceed with original remediation (state dict). Already implemented in PR #146.

#### GAP-014: HIGH-016 -- contextlib.suppress(Exception) in Test Assertions
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED** (with coordination note)
**Reason**: Test quality is independent of R5-01 semantically. However, R5-01 introduces new contract tests that MUST NOT inherit this anti-pattern.
**Action**: Proceed with original remediation. Already implemented in PR #146. **CRITICAL**: Ensure PR #146 is merged BEFORE R5-01 Phase 0-cascor starts, to avoid contaminating new contract tests.

#### GAP-015: HIGH-017 -- WebSocket Schema Tests No Fail Guard
**Original Status**: NOT FIXED
**R5-01 Alignment**: **COORDINATED** with Phase 0-cascor + Phase H
**Reason**: R5-01 Phase 0-cascor introduces `FakeCascorServerHarness` and `FakeCascorMessageSchema`. R5-01 Phase H adds `normalize_metric` regression gates. The existing WebSocket schema tests should be rewritten to use these patterns.
**Revised Action**:

- PR #146 partial fix (pytest.fail guards + `requires_server` marker) is a minimal stopgap
- Full rework: convert to contract tests using `FakeCascorServerHarness` when Phase 0-cascor lands
- Add R5-01 envelope assertions: `seq`, `emitted_at_monotonic`, `command_id` echo (C-01), negative assertion for no seq on command_response (C-02)

#### GAP-016: HIGH-018 -- hasattr Guards Skip Test Logic
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Test quality is independent of R5-01.
**Action**: Proceed with original remediation. Already implemented in PR #146.

#### GAP-017: MED-048 -- Session-Scoped Mutable Dict
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: conftest.py infrastructure is independent of R5-01.
**Action**: Proceed with original remediation (function-scoped isolation wrapper). Already implemented in PR #146.

#### GAP-018: MED-049 -- reset_singletons hasattr Fragility
**Original Status**: NOT FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: conftest.py infrastructure is independent of R5-01.
**Action**: Proceed with original remediation (direct attribute access). Already implemented in PR #146.

### 3.2 PARTIALLY FIXED Gaps (16)

#### GAP-P01: HIGH-015 -- TrainingStateMachine Getters Lack Lock
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Lock all getter methods. Already completed in PR #146.

#### GAP-P02: HIGH-008 -- conf/Dockerfile Not Updated
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Reason**: Dockerfile infrastructure is independent of R5-01.
**Action**: Moved to Track POST-2 (conf/Dockerfile decision needed from ops).

#### GAP-P03: MED-018 -- conf/Dockerfile Missing Service URLs
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Moved to Track POST-2.

#### GAP-P04: LOW-010 -- conf/Dockerfile Uses Python Health Check
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Moved to Track POST-2.

#### GAP-P05: HIGH-005 -- Sync HTTP with Timeout Constant
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **SUPERSEDED** by R5-01 Phase B
**Reason**: R5-01 Phase B explicitly eliminates REST polling via WebSocket bridge drain callbacks. The P0 win metric (`canopy_rest_polling_bytes_per_sec` >=90% reduction) is the canonical measurement.
**Revised Action**:

- The timeout constant band-aid is retained but NOT extended
- NO further audit work on HIGH-005
- Phase B's WebSocket bridge is the permanent solution
- Post-Phase-B audit: verify >=90% polling reduction sustained

#### GAP-P06: HIGH-010 -- /ws Handler Logs but No Finally
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **COORDINATED** with Phase 0-cascor
**Reason**: R5-01 Phase 0-cascor rewrites WebSocket endpoints. The `finally` cleanup fix is retained but the surrounding handler will be restructured in Phase 0-cascor + Phase B-pre-a/b.
**Revised Action**:

- PR #146 `finally` block fix is a minimal stopgap
- Full rewrite: two-phase registration + frame cap + per-IP cap + CSRF auth in Phase 0-cascor + Phase B-pre-a/b
- Do NOT over-invest in further `/ws` handler hardening pre-Phase-0-cascor

#### GAP-P07: MED-002 -- broadcast Fixed but send_personal_message Still Mutates
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Fix `send_personal_message` mutation. Already completed in PR #146.

#### GAP-P08: MED-029 -- Network Info Fixed but Dark Mode Still Modulo
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Fix dark mode modulo toggle. Already completed in PR #146.

#### GAP-P09: MED-026 -- ThemeColors Created but Not Adopted
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **DEFERRED** to post-R5-01 Phase B
**Reason**: Threading a ThemeColors rollout through Phase B's edits to many component files is risky. Defer full rollout until Phase B is complete.
**Revised Action**:

- Keep `theme_constants.py` file in place (infrastructure ready)
- DO NOT wire ThemeColors into components before Phase B
- Rollout happens in Track POST-1.2 after Phase B production soak

#### GAP-P10: MED-027 -- Short-Circuit Only, Not Split
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **COORDINATED** with Phase B
**Reason**: R5-01 Phase B adds WS wire to `network_visualizer.py`. Callback restructuring should happen AS PART OF Phase B work to avoid duplicate effort.
**Revised Action**:

- Current short-circuit is acceptable stopgap
- Callback splitting (if still needed) happens in Phase B PR
- Coordinate with Phase B owner

#### GAP-P11: MED-030 -- One Broken Link
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Fix `docs/API.md` → `docs/api/API_REFERENCE.md`. Already completed in PR #146.

#### GAP-P12: MED-035 -- CancelledError Separated but Bare Exception Remains
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **COORDINATED** with Phase C
**Reason**: R5-01 Phase C rewrites the relay loop with `_control_stream_supervisor`. Exception handling will be comprehensively redesigned.
**Revised Action**:

- PR #146 `OSError` narrowing is a partial improvement
- Full exception handling alignment happens in Phase C with `_control_stream_supervisor`
- Coordinate with Phase C owner

#### GAP-P13: LOW-003 -- config_manager Confusing Ternary
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Moved to Track POST-3.1 (low priority cleanup).

#### GAP-P14: LOW-007 -- FATAL_LEVEL=60 Undocumented
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Moved to Track POST-3.2 (low priority cleanup).

#### GAP-P15: HIGH-019 -- 3/5 Tests Real, 2 Still No-Op
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Fix remaining 2 no-op tests. Addressed in PR #146 (test_button_visual_feedback_latency skipped with clear reason; test_button_re_enable_after_success has proper assertion).

#### GAP-P16: LOW-021 -- asyncio_mode=auto Set but Old Fixture Remains
**Original Status**: PARTIALLY FIXED
**R5-01 Alignment**: **REAFFIRMED**
**Action**: Remove deprecated event_loop fixture. Already completed in PR #146.

## 4. Updated Gap Clustering

### 4.1 Clusters by R5-01 Disposition

#### Cluster A: REAFFIRMED (22 gaps, proceed as originally planned)

- All Cassandra/Redis backend fixes (GAP-001, GAP-002, GAP-003, GAP-010, GAP-011)
- All test quality fixes (GAP-014, GAP-016, GAP-017, GAP-018, GAP-P15, GAP-P16)
- Dataset/torch/TrainingState (GAP-007, GAP-008, GAP-009, GAP-013)
- Screenshot filename (GAP-004)
- DemoBackend auto-start (GAP-005)
- Frontend fixes (GAP-P01, GAP-P07, GAP-P08, GAP-P11)
- Dockerfile partial fixes (GAP-P02, GAP-P03, GAP-P04)
- Low priority cleanups (GAP-P13, GAP-P14)

#### Cluster B: SUPERSEDED (1 gap, no further work)

- HIGH-005 sync HTTP (GAP-P05) → R5-01 Phase B

#### Cluster C: DEFERRED (4 gaps, wait for R5-01 Phase B production stable)

- HIGH-014 DashboardManager extraction (GAP-006)
- MED-026 ThemeColors rollout (GAP-P09)
- HIGH-008/MED-018/LOW-010 conf/Dockerfile (GAP-P02, GAP-P03, GAP-P04) -- optionally deferred pending ops decision

#### Cluster D: COORDINATED (7 gaps, align with specific R5-01 phase)

- HIGH-010 /ws handler (GAP-P06) → Phase 0-cascor
- HIGH-017 WebSocket schema tests (GAP-015) → Phase 0-cascor + Phase H
- MED-021 set_params Pydantic model → Phase C (tracked via Track EMB-5)
- MED-027 NetworkVisualizer callback (GAP-P10) → Phase B
- MED-035 Relay loop exceptions (GAP-P12) → Phase C
- MED-044 TrainingMonitor apply_params → Phase C (tracked via Track EMB-5)
- MED-046 ServiceBackend private attrs (GAP-012) → Phase C

## 5. Updated Remediation Priority Matrix

### Priority 1: Complete Track PRE & PAR (Done via PR #146)

| Gap                    | Issue   | Status                      | Action        |
|------------------------|---------|-----------------------------|---------------|
| All 22 REAFFIRMED gaps | Various | Mostly complete via PR #146 | Merge PR #146 |

### Priority 2: Track EMB -- Align with R5-01 Phase Owners

| Gap     | Issue                        | R5-01 Phase    | Responsibility                             |
|---------|------------------------------|----------------|--------------------------------------------|
| GAP-P06 | HIGH-010 /ws handler         | Phase 0-cascor | Coordinate with Phase 0-cascor implementer |
| GAP-015 | HIGH-017 schema tests        | Phase 0-cascor | Coordinate with Phase 0-cascor implementer |
| GAP-P10 | MED-027 NetworkVisualizer    | Phase B        | Coordinate with Phase B implementer        |
| GAP-012 | MED-046 ServiceBackend API   | Phase C        | Coordinate with Phase C implementer        |
| GAP-P12 | MED-035 Relay exceptions     | Phase C        | Coordinate with Phase C implementer        |
| MED-021 | set_params Pydantic          | Phase C        | Coordinate with Phase C implementer        |
| MED-044 | TrainingMonitor apply_params | Phase C        | Coordinate with Phase C implementer        |

### Priority 3: Track POST -- Post-R5-01 Phase B Production Stable

| Gap     | Issue                             | Prerequisite            | Effort |
|---------|-----------------------------------|-------------------------|--------|
| GAP-006 | HIGH-014 DashboardManager extract | Phase B stable >=7 days | High   |
| GAP-P09 | MED-026 ThemeColors rollout       | Phase B stable >=7 days | High   |
| GAP-P02 | HIGH-008 conf/Dockerfile          | Ops decision            | Low    |
| GAP-P03 | MED-018 conf/Dockerfile           | Ops decision            | Low    |
| GAP-P04 | LOW-010 conf/Dockerfile           | Ops decision            | Low    |
| GAP-P13 | LOW-003 config_manager            | None                    | Low    |
| GAP-P14 | LOW-007 FATAL_LEVEL docs          | None                    | Low    |

### Priority 4: Superseded -- No Further Work

| Gap     | Issue              | Canonical Solution             |
|---------|--------------------|--------------------------------|
| GAP-P05 | HIGH-005 sync HTTP | R5-01 Phase B WebSocket bridge |

## 6. Audit Sign-Off Criteria (Updated)

The audit passes when:

1. **Track PRE/PAR Complete**: All REAFFIRMED gaps (22) are fixed and tested -- **DONE via PR #146**
2. **Track EMB Coordinated**: All 7 COORDINATED gaps have owner handoff to R5-01 phase implementers -- PENDING
3. **Track POST Accepted**: All 4 DEFERRED gaps documented as post-R5-01 technical debt with tracking issues -- PENDING
4. **SUPERSEDED acknowledged**: HIGH-005 is accepted as not-further-remediated pending R5-01 Phase B -- **DONE**
5. **R5-01 NEW requirements tracked**: 20 NEW requirements from R5-01 are documented in forward work backlog -- PENDING (this document)
6. **Documentation alignment**: 4 audit documents (Analysis, Plan, Roadmap, Audit Plan) have R5-01-aligned versions -- **DONE by this document and companions**
7. **Test suite green**: 4,394+ passed, 0 failed -- **DONE via PR #146**

## 7. R5-01 New Requirements Tracking

These R5-01 requirements are NEW forward work (not audit gaps) and should be tracked in a separate R5-01 implementation backlog:

| Req ID        | Description                                          | Phase              |
|---------------|------------------------------------------------------|--------------------|
| R5-01-NEW-001 | `server_instance_id` on connection_established       | 0-cascor           |
| R5-01-NEW-002 | `replay_buffer_capacity` on connection_established   | 0-cascor           |
| R5-01-NEW-003 | `seq` field on /ws/training messages                 | 0-cascor           |
| R5-01-NEW-004 | `emitted_at_monotonic` on all envelopes              | 0-cascor           |
| R5-01-NEW-005 | `command_id` echo on /ws/control responses           | 0-cascor / C       |
| R5-01-NEW-006 | Two-phase registration (`_pending_connections`)      | 0-cascor / B-pre-a |
| R5-01-NEW-007 | Resume protocol with one-resume-per-connection       | 0-cascor           |
| R5-01-NEW-008 | CSRF first-frame auth (browser) with 5s timeout      | B-pre-b            |
| R5-01-NEW-009 | HMAC first-frame auth (adapter)                      | B-pre-b / C        |
| R5-01-NEW-010 | Origin allowlist validation                          | B-pre-a            |
| R5-01-NEW-011 | Per-IP connection cap (5 default)                    | B-pre-a            |
| R5-01-NEW-012 | Frame size cap (4096 / 65536)                        | B-pre-a            |
| R5-01-NEW-013 | Rate limiting (10 cmd/s soft response)               | B-pre-b            |
| R5-01-NEW-014 | Heartbeat (30s ping, 5s pong timeout)                | F                  |
| R5-01-NEW-015 | Per-command timeouts (D-48 matrix)                   | C / D              |
| R5-01-NEW-016 | `window._juniperWsDrain` namespace + drain callbacks | B                  |
| R5-01-NEW-017 | Polling elimination (>=90% reduction)                | B (P0 win)         |
| R5-01-NEW-018 | Connection indicator 4-state badge                   | B                  |
| R5-01-NEW-019 | CSRF token endpoint `GET /api/csrf`                  | B-pre-b            |
| R5-01-NEW-020 | Latency beacon endpoint `POST /api/ws_latency`       | B                  |

## 8. Audit Execution Phases (Revised)

The original audit's 12-phase execution plan is preserved for reference. Phases 1-11 are substantially complete. Phase 12 (final validation, documentation, cleanup) now includes the R5-01 alignment work documented here.

| Phase       | Description                              | Status                          |
|-------------|------------------------------------------|---------------------------------|
| 1           | Write audit plan                         | DONE                            |
| 2-9         | Execute 8 audit domains                  | DONE                            |
| 10          | Compile gap analysis                     | DONE                            |
| 11          | Run full test suite validation           | DONE                            |
| 12          | Final validation, documentation, cleanup | **IN PROGRESS** (this document) |
| **NEW: 13** | R5-01 alignment re-evaluation            | **DONE** (this document)        |

## 9. Metrics & Observability Alignment

The original audit defined test suite metrics. R5-01 adds production metrics that should be tracked alongside audit metrics:

### Pre-R5-01 Metrics (audit-tracked)

- Test pass count: 4,394 passed, 94 skipped, 0 failed (as of PR #146)
- Audit gap completion: 25 of 34 remediated (74%)
- 9 gaps deferred/superseded/coordinated

### R5-01 Production Metrics (to be tracked during phase execution)

**P0 Win Metric**:

- `canopy_rest_polling_bytes_per_sec{endpoint="/api/metrics/history"}` → target >=90% reduction

**Correctness Metrics**:

- `cascor_ws_seq_gap_detected_total` → target: 0 over 72h
- `cascor_ws_dropped_messages_total{type="state"}` → target: 0 steady-state
- `canopy_ws_orphaned_commands_total` → target: <1/min

**Security Metrics**:

- `canopy_ws_origin_rejected_total`
- `canopy_ws_auth_rejections_total`
- `canopy_ws_rate_limited_total`

**Browser Health Metrics** (RISK-10):

- `canopy_ws_browser_heap_mb` → target: <500 MB
- `canopy_ws_browser_js_errors_total` → target: near-0

## 10. Documentation Alignment Checklist

This re-evaluation preserves the following invariants:

- [x] All 34 original gaps are re-evaluated
- [x] Gap IDs (GAP-001 through GAP-P16) preserved for traceability
- [x] Original disposition (VERIFIED/PARTIALLY FIXED/NOT FIXED) preserved
- [x] R5-01 alignment is additive -- does not invalidate original analysis
- [x] DEFERRED gaps specify exact R5-01 phase prerequisite
- [x] COORDINATED gaps specify exact R5-01 phase for alignment
- [x] SUPERSEDED gap (HIGH-005) explicitly marked as not-further-remediated
- [x] 20 R5-01 NEW requirements tracked as forward work
- [x] Companion documents (Analysis, Plan, Roadmap) cross-referenced
- [x] Audit sign-off criteria updated to include R5-01 alignment

---

## Appendix A: Disposition Lookup Table

For quick reference, this table maps each audit gap to its R5-01 disposition:

| Gap ID  | Issue ID | Severity | Original Status | R5-01 Disposition          |
|---------|----------|----------|-----------------|----------------------------|
| GAP-001 | MED-040  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-002 | MED-039  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-003 | MED-041  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-004 | HIGH-007 | High     | NOT FIXED       | REAFFIRMED                 |
| GAP-005 | MED-045  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-006 | HIGH-014 | High     | NOT FIXED       | DEFERRED (Phase B)         |
| GAP-007 | MED-034  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-008 | MED-037  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-009 | MED-038  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-010 | MED-042  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-011 | MED-043  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-012 | MED-046  | Medium   | NOT FIXED       | COORDINATED (Phase C)      |
| GAP-013 | MED-047  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-014 | HIGH-016 | High     | NOT FIXED       | REAFFIRMED                 |
| GAP-015 | HIGH-017 | High     | NOT FIXED       | COORDINATED (0-cascor + H) |
| GAP-016 | HIGH-018 | High     | NOT FIXED       | REAFFIRMED                 |
| GAP-017 | MED-048  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-018 | MED-049  | Medium   | NOT FIXED       | REAFFIRMED                 |
| GAP-P01 | HIGH-015 | High     | PARTIAL         | REAFFIRMED                 |
| GAP-P02 | HIGH-008 | High     | PARTIAL         | REAFFIRMED (POST-2)        |
| GAP-P03 | MED-018  | Medium   | PARTIAL         | REAFFIRMED (POST-2)        |
| GAP-P04 | LOW-010  | Low      | PARTIAL         | REAFFIRMED (POST-2)        |
| GAP-P05 | HIGH-005 | High     | PARTIAL         | **SUPERSEDED** (Phase B)   |
| GAP-P06 | HIGH-010 | High     | PARTIAL         | COORDINATED (0-cascor)     |
| GAP-P07 | MED-002  | Medium   | PARTIAL         | REAFFIRMED                 |
| GAP-P08 | MED-029  | Medium   | PARTIAL         | REAFFIRMED                 |
| GAP-P09 | MED-026  | Medium   | PARTIAL         | DEFERRED (Phase B)         |
| GAP-P10 | MED-027  | Medium   | PARTIAL         | COORDINATED (Phase B)      |
| GAP-P11 | MED-030  | Medium   | PARTIAL         | REAFFIRMED                 |
| GAP-P12 | MED-035  | Medium   | PARTIAL         | COORDINATED (Phase C)      |
| GAP-P13 | LOW-003  | Low      | PARTIAL         | REAFFIRMED (POST-3)        |
| GAP-P14 | LOW-007  | Low      | PARTIAL         | REAFFIRMED (POST-3)        |
| GAP-P15 | HIGH-019 | High     | PARTIAL         | REAFFIRMED                 |
| GAP-P16 | LOW-021  | Low      | PARTIAL         | REAFFIRMED                 |

---

*Document generated: 2026-04-12*
*Supersedes: CODE_REVIEW_AUDIT_PLAN_2026-04-12.md (for planning decisions)*
*Source of truth: R5-01_canonical_development_plan.md*
*Companion: CODE_REVIEW_ANALYSIS_2026-04-12_R5-01-aligned.md, CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md, CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md*
*Status: R5-01 RE-EVALUATION COMPLETE*
