# Juniper Canopy -- Code Review Analysis (R5-01 Aligned)

**Date**: 2026-04-12
**Version Reviewed**: 0.4.0
**Source of Truth**: [R5-01 Canonical Development Plan](../../juniper-ml/notes/interface_proposals/R5-01_canonical_development_plan.md)
**Supersedes**: [CODE_REVIEW_ANALYSIS_2026-04-04.md](CODE_REVIEW_ANALYSIS_2026-04-04.md)

---

## 1. Purpose

This document re-evaluates all 99+ issues from the original 2026-04-04 code review analysis against the **R5-01 Canonical Development Plan** -- the authoritative source of truth for the juniper-canopy <-> juniper-cascor interface. The canonical plan defines an 11-phase implementation of the WebSocket messaging system, security model, and architectural contracts that juniper-canopy must conform to.

This re-evaluation does NOT invalidate the original analysis. Instead, it:

1. **Reaffirms** issues that are independent of R5-01 and should still be fixed
2. **Supersedes** issues where R5-01 provides a more comprehensive solution
3. **Defers** issues where fixing now would conflict with R5-01 phase work
4. **Coordinates** issues that must align with specific R5-01 phases
5. **Modifies** issues where R5-01 changes the recommended fix approach

The original issue IDs (CRIT-001, HIGH-001, etc.) are preserved for traceability.

## 2. Canonical Constraints That Affect the Audit

R5-01 establishes 15 load-bearing constraints that override or modify prior analysis:

| #  | Constraint                                       | Decision ID      | Impact on Audit                                       |
|----|--------------------------------------------------|------------------|-------------------------------------------------------|
| 1  | `command_id` everywhere (NOT `request_id`)       | D-02, C-01       | Any fix touching WS correlation must use `command_id` |
| 2  | No `seq` on `command_response`                   | D-03, C-02       | Control path is seq-free by design                    |
| 3  | `server_instance_id` on `connection_established` | D-15, C-06       | New required field; forces full resync on crash       |
| 4  | REST preserved forever                           | D-21, D-54, D-56 | NO deprecation of REST endpoints, ever                |
| 5  | `replay_buffer_capacity` advertised              | D-16, C-07       | Client-visible capacity in handshake                  |
| 6  | Two-phase registration (`_pending_connections`)  | D-14, C-08       | WS connect path restructured                          |
| 7  | CSRF + HMAC auth first-frame                     | D-29, M-SEC-02   | All WS endpoints require first-frame auth             |
| 8  | `ws_security_enabled=True` default, CI-enforced  | D-10, C-27       | Positive-sense security flag                          |
| 9  | `set_params` timeout = 1.0s; per-command in D-48 | D-01, C-03       | Specific timeouts mandated                            |
| 10 | Backpressure: `drop_oldest_progress_only`        | D-19             | State events NEVER dropped; progress is               |
| 11 | Single-bucket rate limit 10 cmd/s, soft response | D-33             | Rate limit is not a close                             |
| 12 | One-resume-per-connection                        | D-30             | Second resume → close 1003                            |
| 13 | Per-IP connection cap = 5 (configurable)         | D-24             | Per-IP enforcement mandatory                          |
| 14 | Replay buffer = 1024 entries default             | D-35, C-05       | Bounded by design                                     |
| 15 | Kill-switch MTTR <=5 min, tested in staging      | D-53             | Every phase has drilled kill switches                 |

These 15 constraints are the "north star" for re-evaluation. Any audit finding that conflicts with them requires rework.

## 3. Issue Re-Evaluation by Category

### 3.1 Alignment Category Definitions

| Category        | Meaning                                         | Action                                  |
|-----------------|-------------------------------------------------|-----------------------------------------|
| **REAFFIRMED**  | Issue is independent of R5-01; fix still needed | Proceed as originally planned           |
| **SUPERSEDED**  | R5-01 provides a more comprehensive solution    | Remove prior fix; wait for R5-01 phase  |
| **DEFERRED**    | Fix would conflict with R5-01 phase work        | Delay until after specified R5-01 phase |
| **COORDINATED** | Fix must align with specific R5-01 phase        | Execute as part of R5-01 phase          |
| **MODIFIED**    | R5-01 changes the recommended fix               | Apply R5-01-compliant variant           |

### 3.2 Critical Issues

#### CRIT-001 -- Path Traversal in Snapshot Endpoints
**Category**: REAFFIRMED
**R5-01 Impact**: None -- snapshot endpoints are out of scope for the canopy-cascor interface.
**Action**: Original fix (sanitize + path confinement) remains correct.

#### CRIT-002 -- Thread-Unsafe CallbackContextAdapter
**Category**: REAFFIRMED
**R5-01 Impact**: None -- `contextvars` solution aligns with R5-01's thread-safety philosophy.
**Action**: Original fix (ContextVar migration) remains correct.

#### CRIT-003 -- Lockfile Extras Mismatch
**Category**: REAFFIRMED
**R5-01 Impact**: None -- CI/dependency concern unrelated to interface.
**Action**: Original fix (add `--extra observability`) remains correct. Note: R5-01 Phase A-SDK will require pinning `juniper-cascor-client>=<version>` same-day, which should be coordinated with lockfile update flow.

### 3.3 High Severity Issues

#### HIGH-001 -- API Key Timing Attack
**Category**: REAFFIRMED (reinforced by R5-01)
**R5-01 Impact**: R5-01 Section 4.1 explicitly mandates `hmac.compare_digest` for both browser CSRF and adapter HMAC auth. This is the same fix pattern.
**Action**: Original fix remains correct. Document the alignment with R5-01's auth model for future audit traceability.

#### HIGH-002 -- Exception Handler Leaks Internal Details
**Category**: REAFFIRMED (reinforced by R5-01)
**R5-01 Impact**: R5-01 Section 4.3 mandates opaque error strings (M-SEC-06). Generic messages + server-side logging is the canonical pattern. R5-01 also requires CRLF escaping in audit logs (M-SEC-07) -- this should be added to any logger touched by this fix.
**Action**: Original fix remains correct. Add CRLF escaping where logs echo client input.

#### HIGH-003 -- Rate Limiter Memory Leak
**Category**: REAFFIRMED (reinforced by R5-01)
**R5-01 Impact**: R5-01 Phase B-pre-b introduces a single-bucket leaky bucket (10 tokens, 10 cmd/sec refill) for WebSocket control. This is a DIFFERENT rate limiter from HIGH-003's HTTP-level limiter. Both should exist. Per R5-01 D-33, WS rate limit is a soft response (not a close).
**Action**: Original HTTP-level rate limiter fix remains correct. **Note**: A second, WS-level rate limiter must be built in Phase B-pre-b -- do not delete the HTTP one.

#### HIGH-004 -- threading.Event Replacement Race
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix (`_stop.clear()`) remains correct.

#### HIGH-005 -- Synchronous Blocking HTTP in Dashboard Callbacks
**Category**: **SUPERSEDED**
**R5-01 Impact**: **Major**. R5-01 Phase B explicitly eliminates REST polling in favor of WebSocket bridge drain callbacks. The `canopy_rest_polling_bytes_per_sec` metric is the P0 win gate (>=90% reduction). The "partial fix" via `FAST_API_TIMEOUT_SECONDS` constant is a band-aid that will be removed when Phase B is complete.
**R5-01 Canonical Fix**: Phase B implements:

- `dcc.Store(id='ws-metrics-buffer')` with drain callback from `window._juniperWsDrain.drainMetrics()`
- Polling-toggle pattern: return `no_update` when WS connected; REST fallback at 1 Hz when disconnected
- `enable_browser_ws_bridge` feature flag
- Clientside callback with `Plotly.extendTraces(graphId, update, [0,1,2,3], 5000)` and `uirevision: "metrics-panel-v1"`
**Action**: **Do NOT perform further work on HIGH-005 independently.** The band-aid timeout constant from the prior audit remediation is acceptable as a stopgap. The permanent solution is R5-01 Phase B (`dashboard_manager.py` lines 2388-2421 refactor). Wait for Phase B.

#### HIGH-006 -- _api_url() Uses Flask Request Context Unsafely
**Category**: REAFFIRMED
**R5-01 Impact**: None -- settings-based URL construction is the canonical pattern.
**Action**: Original fix remains correct.

#### HIGH-007 -- NetworkVisualizer Screenshot Filename Frozen
**Category**: REAFFIRMED
**R5-01 Impact**: None, but note that R5-01 Phase B will edit `network_visualizer.py` to add minimum WS wire for `topology` and `cascade_add` messages. The screenshot filename fix should be merged BEFORE Phase B to avoid conflict.
**Action**: Original fix remains correct. Merge before Phase B starts.

#### HIGH-008 -- Debug Mode in Docker Production Image
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix (root Dockerfile) remains correct. The `conf/Dockerfile` partial-fix gap is still valid and should be resolved independently.

#### HIGH-009 -- Bandit Config Fragmentation
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix remains correct.

#### HIGH-010 -- WebSocket /ws Endpoint Silent Exception Loop
**Category**: **COORDINATED** with Phase 0-cascor
**R5-01 Impact**: R5-01 Phase 0-cascor adds structured error handling, close codes, and termination semantics to WebSocket endpoints. Phase B-pre-a adds per-IP caps, frame size caps, origin validation. Phase B-pre-b adds CSRF and rate limiting. The `/ws` endpoint will be SUBSTANTIALLY rewritten.
**Canonical Fix**: Phase 0-cascor + Phase B-pre-a + Phase B-pre-b combined implement:

- Two-phase registration (`_pending_connections` → `active_connections`)
- Frame size cap (4096 bytes on `/ws/training`)
- Per-IP cap (5 default)
- Origin validation
- CSRF first-frame auth (5s timeout)
- Rate limiting (10 cmd/s, soft response)
- Structured close codes (1003, 1008, 1009, 1013)
- `finally` cleanup block (exception-safe disconnect)
**Action**: The existing `finally` block remediation is a minimal stopgap; it's acceptable but will be rewritten entirely in Phase 0-cascor + Phase B-pre-a/b. Do NOT over-invest in hardening the current handler.

#### HIGH-011 -- Hardcoded Version Strings
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix (`importlib.metadata.version`) remains correct.

#### HIGH-012 -- Publish Workflow Missing Permission
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix remains correct.

#### HIGH-013 -- Duplicate Phase Band/Marker Logic
**Category**: REAFFIRMED
**R5-01 Impact**: None -- metrics_panel.py edits in Phase B are limited to clientside callbacks, not phase band rendering.
**Action**: Original fix remains correct.

#### HIGH-014 -- DashboardManager God Class (3007 lines)
**Category**: **DEFERRED** until after R5-01 Phase B
**R5-01 Impact**: **Major conflict risk**. R5-01 Phase B makes substantial edits to `dashboard_manager.py`:

- Lines 1490-1526 deletion (dead raw-WS code)
- 5 new `dcc.Store` instances
- Refactored `_update_metrics_store_handler` (lines 2388-2421)
- Drain callbacks for metrics/state/topology/cascade_add/candidate_progress
- Delete `window._juniper_ws_*` globals
- Apply polling-toggle pattern to multiple handlers

Extracting DashboardManager into sub-modules NOW would create massive merge conflicts with Phase B. The extraction is also "High" effort (the roadmap target was "below 2,000 lines" and current is 3,007).

**Action**: **DEFER extraction until after R5-01 Phase B exits production.** The prior audit's recommendation to extract is correct in principle but incorrect in timing. Revisit after Phase B is stable in production (post flag-flip soak).

**Interim Action**: Document the current 3,007-line state as an accepted technical debt item with dependency on Phase B completion. Create a tracking issue tagged `depends-on:phase-B-post-flip`.

#### HIGH-015 -- TrainingStateMachine No Thread Safety
**Category**: REAFFIRMED
**R5-01 Impact**: None -- this is backend state management, not interface concerns.
**Action**: Original fix (threading.Lock on all state mutations + getters) remains correct. The partial-fix gap (getters lacked lock) should be resolved independently.

#### HIGH-016 -- False Positive Tests Using contextlib.suppress(Exception)
**Category**: REAFFIRMED
**R5-01 Impact**: None -- test quality is independent. However, R5-01 introduces new contract tests (`@pytest.mark.contract`) that MUST NOT use suppress patterns.
**Action**: Original fix remains correct. Extend the AST lint rule (when introduced) to reject `contextlib.suppress(Exception)` around assertions in all tests, including forthcoming contract tests.

#### HIGH-017 -- WebSocket Schema Tests No Fail Guard
**Category**: **COORDINATED** with Phase 0-cascor + Phase H
**R5-01 Impact**: R5-01 Phase 0-cascor introduces `FakeCascorMessageSchema` and contract tests. R5-01 Phase H adds `normalize_metric` regression gates with CODEOWNERS. The existing WebSocket schema tests should be aligned with these patterns.
**Canonical Fix**: Schema tests become contract tests:

- Enforce envelope field presence (`seq`, `emitted_at_monotonic`, `server_instance_id`)
- Validate command_id echo (C-01)
- Validate NO seq on command_response (C-02 negative assertion)
- Use `FakeCascorServerHarness` rather than live server dependencies
**Action**: The existing `pytest.fail` guards remediation is a minimal improvement but insufficient. Rework tests to use `FakeCascorServerHarness` and add R5-01 contract assertions when Phase 0-cascor lands.

#### HIGH-018 -- hasattr Guards Silently Skip Test Logic
**Category**: REAFFIRMED
**R5-01 Impact**: None.
**Action**: Original fix remains correct.

#### HIGH-019 -- Performance Test Effectively a No-Op
**Category**: REAFFIRMED
**R5-01 Impact**: None. R5-01 introduces load tests (100 Hz x 60s x 10 clients, p95 < 250ms) as blocking gates for Phase 0-cascor. These are more comprehensive than HIGH-019's button responsiveness test.
**Action**: Original fix remains correct. Button responsiveness test does not overlap with R5-01's WS load tests.

### 3.4 Medium Severity Issues -- Summary Table

To avoid duplication, medium severity issues are summarized in the table below. Full detail is provided only where R5-01 changes the recommended fix.

| ID      | Category      | Description                         | Alignment                               | Action                                                                                                                                                                                                   |
|---------|---------------|-------------------------------------|-----------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| MED-001 | WebSocket     | max_connections not enforced        | **MODIFIED**                            | R5-01 introduces per-IP caps (5 default) which are more important than global max. Keep global limit as secondary defense; per-IP is primary (Phase B-pre-a).                                            |
| MED-002 | WebSocket     | broadcast() mutates message dict    | REAFFIRMED                              | Original fix + send_personal_message fix remain correct.                                                                                                                                                 |
| MED-003 | Security      | CORS allows all methods/headers     | REAFFIRMED                              | HTTP CORS is separate from R5-01's WS origin allowlist. Both needed.                                                                                                                                     |
| MED-004 | Performance   | Sentry traces_sample_rate=1.0       | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-005 | Performance   | Prometheus endpoint cardinality     | REAFFIRMED                              | R5-01 introduces additional Prometheus metrics (see Section 8.5 of canonical plan) that should follow the same route-template pattern.                                                                   |
| MED-006 | Performance   | Blocking probe_dependency           | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-007 | Performance   | Logger factory instance creation    | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-008 | Logic         | ColoredFormatter LogRecord mutation | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-009 | Config        | app_config.yaml version stale       | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-010 | Config        | pyproject.toml header version stale | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-011 | Config        | logging_config.yaml truncate mode   | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-012 | Config        | TRACE level may crash               | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-013 | Config        | CORS allowed_origins YAML syntax    | REAFFIRMED                              | Note: R5-01 WS origin allowlist uses `ws_allowed_origins` (separate setting). Do not conflate.                                                                                                           |
| MED-014 | CI/CD         | pip-audit scans subset              | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-015 | Config        | No [dev] extra                      | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-016 | Docker        | Docker builds outside lockfile      | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-017 | Config        | MyPy strict_optional conflict       | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-018 | Docker        | Docker ENV uses localhost           | REAFFIRMED                              | Original fix (root Dockerfile) remains correct; conf/Dockerfile gap still valid.                                                                                                                         |
| MED-019 | CI/CD         | Codecov config but no upload        | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-020 | Syntax        | Duplicate cn_patience               | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-021 | API Design    | Untyped dict for set_params         | **COORDINATED** with Phase C            | R5-01 Phase C mandates Pydantic model with `extra="forbid"` on cascor side. Canopy adapter routes unknown keys with WARNING. See detailed notes below.                                                   |
| MED-022 | Config        | get_rate_limiter bypasses settings  | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-023 | Logic         | Content-length ValueError           | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-024 | Code Smell    | Dead _create_candidate_pool_display | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-025 | Syntax        | Orphaned candidate callbacks        | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-026 | Code Smell    | Hardcoded colors (500+)             | **DEFERRED** (parallel with Phase B OK) | R5-01 Phase B edits many component files. Threading a ThemeColors rollout through Phase B edits is risky. Defer full rollout until Phase B is complete, but keep the `theme_constants.py` file in place. |
| MED-027 | Architecture  | NetworkVisualizer 10-input callback | **COORDINATED** with Phase B            | R5-01 Phase B adds WS wire to network_visualizer.py. Callback restructure should happen AS PART OF Phase B work.                                                                                         |
| MED-028 | Performance   | time.sleep() blocking               | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-029 | Logic         | Modulo toggle                       | REAFFIRMED                              | Original fix (boolean toggle pattern) remains correct.                                                                                                                                                   |
| MED-030 | UI/UX         | About panel broken link             | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-031 | Code Smell    | _create_empty_plot duplicated       | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-032 | Security      | Security scan bandit inconsistency  | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-033 | Dependencies  | Conda CUDA toolkit bloat            | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-034 | Performance   | Network property HTTP per access    | REAFFIRMED                              | Original TTL cache fix remains correct. Does not interact with R5-01 WS path.                                                                                                                            |
| MED-035 | Best Practice | Relay loop swallows exceptions      | **COORDINATED** with Phase C            | R5-01 Phase C introduces `_control_stream_supervisor` with backoff reconnect and explicit correlation map cleanup. The cascor_service_adapter.py relay loop will be substantially rewritten.             |
| MED-036 | Logic         | ServiceBackend KeyError             | REAFFIRMED                              | Original fix (`"inputs" in data` guard) remains correct.                                                                                                                                                 |
| MED-037 | Architecture  | Hard torch import                   | REAFFIRMED                              | Original fix (lazy import) remains correct.                                                                                                                                                              |
| MED-038 | Logic         | None crash in prepare_dataset       | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-039 | Concurrency   | Cassandra singleton no lock         | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-040 | Security      | Cassandra credentials as attributes | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-041 | Concurrency   | Redis singleton no lock             | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-042 | Logic         | Redis exception sentinel            | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-043 | Resource Leak | Redis force_new connection leak     | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-044 | Logic         | TrainingMonitor apply_params no-op  | **COORDINATED** with Phase C            | R5-01 Phase C introduces real `apply_params` semantics with hot/cold split. See detailed notes below.                                                                                                    |
| MED-045 | Logic         | DemoBackend auto-start              | REAFFIRMED                              | Original fix (document intent) remains correct. R5-01 RISK-08 requires demo mode parity tests.                                                                                                           |
| MED-046 | Architecture  | ServiceBackend private attrs        | **COORDINATED** with Phase C            | R5-01 Phase C extends CascorServiceAdapter for hot/cold param split. Public API exposure should happen as part of Phase C work.                                                                          |
| MED-047 | Logic         | TrainingState name-mangling         | REAFFIRMED                              | Original fix (state dict) remains correct.                                                                                                                                                               |
| MED-048 | Test Infra    | Session-scoped mutable dict         | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |
| MED-049 | Test Infra    | reset_singletons hasattr fragility  | REAFFIRMED                              | Original fix remains correct.                                                                                                                                                                            |

### 3.5 Detailed Notes on Coordinated MED Issues

#### MED-021 -- set_params Pydantic Model (Coordinate with Phase C)

The original audit recommended a simple Pydantic model for the set_params REST endpoint. R5-01 Phase C mandates a more comprehensive solution:

1. **Cascor side** (`extra="forbid"`): Cascor rejects any unknown parameter keys. This is enforced at the schema level (not canopy's concern, but canopy must know the exact valid key set).
2. **Canopy adapter** (`cascor_service_adapter.py`): Splits the parameter dict into:
   - **Hot params (11)**: `learning_rate`, `candidate_learning_rate`, `correlation_threshold`, `candidate_pool_size`, `max_hidden_units`, `epochs_max`, `max_iterations`, `patience`, `convergence_threshold`, `candidate_convergence_threshold`, `candidate_patience`
   - **Cold params (2)**: `init_output_weights`, `candidate_epochs`
   - **Unknown keys**: Logged as WARNING and routed to REST (letting cascor reject them)
3. **Routing logic**: Hot params go via WS `/ws/control` with 1.0s timeout; on timeout/error, fall back to REST. Cold params always go REST.
4. **Correlation**: `command_id` field (NOT `request_id`) required in every command/response pair.

**Action**: The prior audit's simple Pydantic model is a partial fix. Extend to full Phase C implementation:

- Define `_HOT_CASCOR_PARAMS: frozenset[str]` and `_COLD_CASCOR_PARAMS: frozenset[str]` constants
- Build `apply_params(params)` method with hot/cold split
- Add WS-first routing with REST fallback
- Use `command_id` correlation field

#### MED-044 -- TrainingMonitor apply_params No-Op (Coordinate with Phase C)

The prior audit found that `TrainingMonitor.apply_params` was a no-op stub. The fix partially implemented it to record params but not apply them to the backend.

R5-01 Phase C makes this the canonical set_params implementation point. The flow is:

1. Canopy receives `PATCH /api/train/params` or callback slider event
2. `CascorServiceAdapter.apply_params(params)` splits hot/cold
3. Hot params sent via WS `/ws/control` command with 1.0s timeout
4. Cold params sent via REST
5. Response correlated by `command_id`
6. `TrainingMonitor` receives the applied params and records them (this was the original MED-044 stub)

**Action**: Replace the minimal MED-044 fix with the Phase C implementation. The "no-op" state is temporarily acceptable until Phase C.

#### MED-046 -- ServiceBackend Accesses Private CascorServiceAdapter Attributes (Coordinate with Phase C)

The prior audit found ServiceBackend accessing `_client`, `_service_url`, and `_is_cascor_nested` on CascorServiceAdapter. The fix exposed these as public properties.

R5-01 Phase C substantially extends `cascor_service_adapter.py`:

- Adds `_control_stream_supervisor` background task
- Adds `_HOT_CASCOR_PARAMS` and `_COLD_CASCOR_PARAMS` frozensets
- Adds `apply_params(params)` method
- Adds bounded correlation map (max 256 pending, raises `JuniperCascorOverloadError` on overflow)
- Adds `CascorServerFrame` Pydantic model with `extra="allow"` for inbound validation
- Adds `_assign_command_id()` helper

**Action**: The public API exposure (from the prior audit fix) is still correct but insufficient for Phase C. Phase C will add more public methods (`apply_params`, `start_control_stream`, etc.). Plan the public API design holistically.

### 3.6 Low Severity Issues -- Summary

All LOW severity issues are REAFFIRMED. None are affected by R5-01.

| ID Range           | Count | Category                          |
|--------------------|-------|-----------------------------------|
| LOW-001 to LOW-022 | 22    | Independent fixes, all REAFFIRMED |

**Special notes**:

- **LOW-008** (WebSocket message size check): The original value was unspecified. R5-01 mandates **4096 bytes** on `/ws/training` and **65536 bytes** on `/ws/control`. **Modify** the constant `_WS_MAX_MESSAGE_SIZE` to match R5-01: the training endpoint should use 4096, not the current canopy default.

- **LOW-021** (event_loop fixture): R5-01 introduces `FakeCascorServerHarness` for tests. Ensure pytest-asyncio auto mode works correctly with the harness before removing custom event_loop fixture.

## 4. New Issues Introduced by R5-01 Requirements

R5-01 introduces NEW requirements that were not present in the original 2026-04-04 review. These are not "issues" per se but new acceptance criteria:

| New Req ID    | Description                                                          | Maps to R5-01    |
|---------------|----------------------------------------------------------------------|------------------|
| R5-01-NEW-001 | `server_instance_id` field on all `connection_established` envelopes | D-15, C-06       |
| R5-01-NEW-002 | `replay_buffer_capacity` field on `connection_established`           | D-16, C-07       |
| R5-01-NEW-003 | `seq` field on all `/ws/training` messages                           | D-02, C-01       |
| R5-01-NEW-004 | `emitted_at_monotonic` field on all envelopes                        | Phase 0-cascor   |
| R5-01-NEW-005 | `command_id` echo on all `/ws/control` responses                     | D-02, C-01       |
| R5-01-NEW-006 | Two-phase registration (`_pending_connections`)                      | D-14, C-08       |
| R5-01-NEW-007 | Resume protocol with one-resume-per-connection                       | D-30             |
| R5-01-NEW-008 | CSRF first-frame auth (browser) with 5s timeout                      | M-SEC-02         |
| R5-01-NEW-009 | HMAC first-frame auth (adapter)                                      | D-29             |
| R5-01-NEW-010 | Origin allowlist validation (case-insensitive, port-significant)     | M-SEC-01b        |
| R5-01-NEW-011 | Per-IP connection cap (5 default)                                    | D-24             |
| R5-01-NEW-012 | Frame size cap (4096 on /ws/training, 65536 on /ws/control)          | M-SEC-03         |
| R5-01-NEW-013 | Rate limiting (10 cmd/s leaky bucket, soft response)                 | D-33, M-SEC-05   |
| R5-01-NEW-014 | Heartbeat (30s ping, 5s pong timeout)                                | Phase F          |
| R5-01-NEW-015 | Per-command timeouts (D-48 matrix)                                   | D-48             |
| R5-01-NEW-016 | `window._juniperWsDrain` namespace + drain callbacks                 | Phase B          |
| R5-01-NEW-017 | Polling elimination (>=90% reduction)                                | Phase B (P0 win) |
| R5-01-NEW-018 | Connection indicator 4-state badge                                   | Phase B, RISK-08 |
| R5-01-NEW-019 | CSRF token endpoint `GET /api/csrf`                                  | Phase B-pre-b    |
| R5-01-NEW-020 | Latency beacon endpoint `POST /api/ws_latency`                       | Phase B          |

These should be tracked as forward work, not as audit gaps. They represent the R5-01 implementation scope.

## 5. Re-prioritized Severity Distribution

| Severity  | Original | REAFFIRMED | SUPERSEDED | DEFERRED | COORDINATED | MODIFIED |
|-----------|----------|------------|------------|----------|-------------|----------|
| Critical  | 3        | 3          | 0          | 0        | 0           | 0        |
| High      | 19       | 15         | 1          | 1        | 2           | 0        |
| Medium    | 47       | 40         | 0          | 1        | 5           | 1        |
| Low       | 30+      | 30+        | 0          | 0        | 0           | 0        |
| **Total** | **99+**  | **88+**    | **1**      | **2**    | **7**       | **1**    |

**88+ REAFFIRMED issues** represent independent fixes that proceed on their current trajectory.

**1 SUPERSEDED issue** (HIGH-005) is replaced by R5-01 Phase B; no further audit work needed.

**2 DEFERRED issues** (HIGH-014, MED-026) must wait for R5-01 Phase B to complete before remediation.

**7 COORDINATED issues** (HIGH-010, HIGH-017, MED-021, MED-027, MED-035, MED-044, MED-046) require their fix approach to align with specific R5-01 phases.

**1 MODIFIED issue** (MED-001) has its fix approach changed by R5-01 (per-IP caps supersede global max_connections).

## 6. Cross-Reference: Test Suite Impact

The original 4,412 test count is still valid. R5-01 Phase 0-cascor adds ~26 new unit tests, 5 integration tests, 3 chaos tests, and 72-hour soak gates. Phase B adds Playwright E2E tests. Total test suite post-R5-01 is projected at ~4,500+.

Audit-identified test quality issues (HIGH-016/017/018/019) must be resolved BEFORE the R5-01 contract tests land, to avoid repeating the false-positive pattern in new tests.

## 7. Action Summary

| Action                          | Count | Notes                                                           |
|---------------------------------|-------|-----------------------------------------------------------------|
| Proceed as originally planned   | 88+   | REAFFIRMED issues                                               |
| Cancel / do not remediate       | 1     | HIGH-005 (band-aid retained, canonical fix via Phase B)         |
| Defer until after Phase B       | 2     | HIGH-014, MED-026                                               |
| Align with specific R5-01 phase | 7     | HIGH-010, HIGH-017, MED-021, MED-027, MED-035, MED-044, MED-046 |
| Modify fix approach             | 1     | MED-001 (defer to per-IP caps)                                  |
| Track as new forward work       | 20    | R5-01-NEW-001 through R5-01-NEW-020                             |

## 8. Validation Checklist

This re-evaluation preserves the following invariants:

- [x] All 99+ original issue IDs are preserved for traceability
- [x] Independent issues (not touching WS/interface) are REAFFIRMED
- [x] R5-01 supersession only applies where the canonical plan provides a comprehensive fix
- [x] DEFERRALS are justified by merge conflict risk, not by avoidance
- [x] COORDINATIONS specify exact R5-01 phase alignment
- [x] No new audit issues are invented; R5-01 requirements are tracked as "NEW" (forward work)
- [x] Test count claims remain consistent with prior audit

---

*Document generated: 2026-04-12*
*Supersedes: CODE_REVIEW_ANALYSIS_2026-04-04.md (for planning decisions)*
*Source of truth: R5-01_canonical_development_plan.md*
*Companion: CODE_REVIEW_PLAN_2026-04-12_R5-01-aligned.md, CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-12_R5-01-aligned.md, CODE_REVIEW_AUDIT_PLAN_2026-04-12_R5-01-aligned.md*
