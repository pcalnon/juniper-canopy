# Juniper-Canopy Frontend Regressions & Gaps — Remediation Plan (2026-05-30)

* **Author**: Paul Calnon (drafted by Claude Code, Opus 4.8)
* **Status**: DRAFT — investigation complete (static analysis); awaiting Phase 0 live reproduction
* **Scope**: Four user-reported regressions/gaps in the juniper-canopy Dash UI and its interaction with juniper-cascor, observed on the **deployed docker stack** (juniper-deploy).
* **Investigated at**: juniper-canopy `main @ d1ad3c5`, juniper-cascor `main @ 2d4a7dd` (read-only static analysis, 4 parallel subagents, 2026-05-30).
* **Supersedes / extends**: [`notes/FRONTEND_ISSUES_PLAN_2026-05-09.md`](../FRONTEND_ISSUES_PLAN_2026-05-09.md) (the six-issue effort whose partial fixes produced several of the symptoms below) and its Phase-2 companion [`notes/ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09.md`](../ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09.md).
* **Working branch / worktree**: `fix/frontend-regressions-2026-05-30` @ `worktrees/juniper-canopy--fix--frontend-regressions-2026-05-30--20260530-1446--d1ad3c5a`.

## Revisions

| Date       | Rev  | Change                                                                                  |
|------------|------|-----------------------------------------------------------------------------------------|
| 2026-05-30 | v0.1 | Initial plan. Four issues; lineage to the 2026-05-09 effort; Phase 0 + Phase 1 defined.  |
| 2026-05-30 | v0.2 | Phase 0 executed on the live deployed stack. **#3 reframed**: primary cause is a cascor dual-path / persistent-pool result-collection bug (`expected 40, got 2` → 0 hidden units), not benign convergence. #2a 429 confirmed and is the dominant source of #3's "Error". See §8.1. |
| 2026-05-30 | v0.3 | **#3 PRIMARY fix implemented** in cascor worktree `fix/candidate-result-collection`: Defect 1 (inactivity collection deadline + worker-liveness early-exit) + Defect 2 (`_ensure_worker_pool` reentrancy — reuse a larger live pool). 7 new regression tests + worker-pool/dispatch/parallel suites green under JuniperCascor1. Live end-to-end rerun still pending. |
| 2026-05-30 | v0.4 | cascor #315 pushed + **CI fixed** (Black line-collapse @ ll=512; amended into `4fa606d`). **4 design decisions resolved** (§7): #2a→re-key-by-session + `Retry-After`; #2b/#4→relocate `nn_dataset_*` to dataset surface; #1→keep `layout-state-store`; sequencing→canopy fixes first. Phase 1 execution started. |

---

## 0. Executive summary

Four issues, reported on the **deployed docker stack** (real cascor backend, rate limiting enabled):

| # (this doc) | Symptom | Root-cause family | Confidence | Repo(s) | Lineage |
|---|---------|-------------------|------------|---------|---------|
| **1** | Clicking a tab then another re-opens the previous tab; sometimes autonomous X↔Y toggle. Deterministic Snapshots→Dataset. | Cyclic clientside callback pair on `active_tab` ↔ `layout-state-store`; **reader not equality-guarded** + **two** redundant tab-persistence systems. | High (mechanism); Med (exact determinism) | canopy | **NEW** — not in 2026-05-09 plan. |
| **2** | "Apply Parameters" → often "Rate limited…"; on success "Applied 19 of 27… 8 not yet supported". | (2a) canopy's **own** per-IP 60/min limiter shared with the dashboard's own polling. (2b) handler ships a fixed 27-key dict; 7/8 "unsupported" are *known* canopy-local but never filtered from the toast; + 3 valid params silently dropped by the Pydantic model. | High | canopy | **Partial-fix residue** of old #1/#2 — toast surfaced (PR-2) but never filtered; force-blur shipped for params only. 2a is NEW. |
| **3** | Training runs ~1 iteration → "Completed" for minutes → "Error" + "WS: Reconnecting". | **[Phase 0 §8.1] PRIMARY: cascor drops 38/40 candidate results** (dual-path / persistent-pool bug) → 0 hidden units → premature `mark_completed()`. Secondary: canopy WS **idle-timeout flap** (no keepalive) → "Reconnecting"; the **429** (see #2a) on `/api/status` → "Error". | **Confirmed (cascor)** §8.1 | cascor + canopy | Old #5 (`_pause_event` reset) is **FIXED** (cascor #240/#244) and had a *Paused* terminal state — current #3 is **distinct**. |
| **4** | Modifying a dataset then starting training never loads the new dataset. | Real backend: numeric inputs commit `null` → `n_samples`/`noise` dropped; only the dropdown survives; **Apply-Dataset has no force-blur**. (Demo-only latent: `start()` ignores staged config.) cascor cold-swap wiring itself is correct. | High | canopy | **Partial-fix residue** of old #3 — cold-swap + Phase 2 shipped but defeated by the unfixed numeric-`null` half of old #2. Tightly linked to #2. |

**Key environment fact:** the "Rate limited" 429 (#2a) only fires when `RATE_LIMIT_ENABLED=true` (true in `.env.prod` + compose/Helm defaults, **false** in `./demo`), and "Error"/"Reconnecting" (#3) **cannot occur in demo**. Both confirm the deployed-stack context. #4's *demo* break is therefore a latent side-fix, **not** the user's repro — the operative #4 breaks are the real-backend ones.

**Recommended ordering:** Phase 0 (reproduce & instrument) → Phase 1 (independent canopy wins: #1, #2b, #4-numeric/#2-forceblur, #3-WS-keepalive) → Phase 2 (live/cross-repo: #3-cascor, #3-Error-UX, #2a-ratelimit, full-stack verify).

---

## 1. Lineage — relationship to the 2026-05-09 effort

The current four are largely the **residue of incompletely-closed 2026-05-09 fixes** plus three genuinely new defects. Ground truth from `git log` (canopy + cascor `main`):

| 2026-05-09 issue | What shipped | Residual gap → current issue |
|---|---|---|
| #1 Metaparams don't reach cascor | PR-2 "surface skipped params" (toast); candidate-pool PATCH contract **cascor #241/#243** | Toast was never *filtered* by `_CANOPY_LOCAL_PARAMS` (defined as a doc allowlist, used only by `test_param_map_completeness.py`); dataset/status fields still shipped → **current #2b**. |
| #2 Numeric input typing vs spinner | `debounce=350` (`NUMERIC_INPUT_DEBOUNCE_MS`) + force-blur clientside; validation styling (D) deferred | Force-blur wired to **`apply-params-button` only**, not `apply-dataset-button` → **current #4 (real backend)** + residual #2. |
| #3 Dataset tab doesn't affect training | Cold-swap (PR-7) + full **Phase 2 live swap** (P2-0…P2-7, canopy + cascor #245–#259) | Cold-swap is correct end-to-end on cascor, but the canopy numeric-`null` gap drops `n_samples`/`noise` before staging → **current #4**. |
| #5 Single-iteration auto-pause after stop+reset | **FIXED**: cascor **#240** `normalise _pause_event in reset()` + **#244** pause/stop actually interrupt | Terminal state was *Paused*. **current #3** ends *Completed→Error* → **distinct mechanism**, must still rule out a new regression. |
| #4 UI test sub-suite / #6 sidebar width | PR-9/9.5/10 shipped | Not in scope here (UI harness still can't drive numeric inputs — see §10). |

**Regression suspects for #3/#4 (all 2026-05-29, all touch the adapter/auth/WS path):** canopy `#327` strip `/v1` prefix from 16 cascor-client call sites, `#328` `cascor_ws_origin` + `cascor-client>=0.5.0`, `#329` outbound `X-API-Key`. Phase 0 must check whether any of these altered the training-status/metrics/control-stream path.

---

## 2. Cross-cutting findings

1. **Environment decides #3/#4 manifestation** (see §0). Confirmed deployed stack.
2. **#2 and #4 share a root**: both depend on the two numeric inputs `nn-dataset-elements-input` / `nn-dataset-noise-input`, which are routed *only* through `stage_dataset` (not `set_params`), so they 100% depend on numeric inputs committing — the known `dbc.Input(type=number)` → `null` Dash/React gap. One fix (force-blur on Apply-Dataset + don't-drop-`None`) helps both.
3. **"Completed", "Error", "Reconnecting" are three separate mechanisms** with a common upstream (cascor stopped producing work) — three distinct edits, not one.
4. **Two redundant subsystems are each the bug's enabler**: tabs have two persistence systems; datasets have two disconnected edit UIs.

---

## 3. Issue 1 — Tab feedback loop

**Diagnosis (High).** Entirely clientside (a FastAPI `TestClient` cannot see it):

* `dbc.Tabs(id="visualization-tabs", active_tab=…)` — `dashboard_manager.py:1533`; persisted `dcc.Store(id="layout-state-store", storage_type="local")` — `:1636`.
* **Writer A** `:2327` — `Input(active_tab)` + `State(layout-state-store)` → `Output(layout-state-store)`, **equality-guarded** (`if prev.active_tab === activeTab: no_update`).
* **Reader B** `:2270` — `Input(layout-state-store)` → `Output(active_tab)`, **guarded only by a null check** — *the defect*: it re-asserts the store value even when it equals the shown tab and even when stale.
* **Self-edge C** `:2070` — `Input(active_tab)` → `Output(active_tab)` (writes localStorage, returns `no_update`) — anti-pattern widening the fan-out.
* Legacy restore `:2085` (from localStorage via `params-init-interval`) races B at mount. Five callbacks declare `Output(active_tab, allow_duplicate=True)`.
* **Snapshots→Dataset deterministic** because Snapshots is the heaviest tab (own `dcc.Interval` + `prevent_initial_call=False` table refresh in `hdf5_snapshots_panel.py`), reliably leaving an extra callback round in flight that wins the duplicate-output race. (Exact tick ordering → live network trace to prove.)

**Resolve** — PR **`fix/canopy-tab-feedback-loop`**:
1. **Primary:** add an equality guard to Reader **B** — give it `State(visualization-tabs.active_tab)`; `return no_update` when the store already equals the active tab. Severs the writeback edge.
2. **Structural:** collapse to **one** persistence system — delete the legacy localStorage pair (`:2070`, `:2085`), keep only `layout-state-store`; make restore-from-store fire **only at mount**.
3. De-self-reference C (write to a dedicated sink store) — moot if (2) deletes it.

**Tests / Verify.** Extend source-introspection tests `tests/unit/test_dashboard_manager.py:585-613`: assert ≤1 mount-time `Output(active_tab)` restore callback and that Reader B contains an equality guard (mirror `test_no_self_loop_on_same_tab`). Behavioral proof needs `dash[testing]`/`pytest-dash` or a manual browser run watching `_dash-update-component` POSTs cease after a tab settles.

**Phase 0 questions.** Confirm the exact Snapshots→Dataset interleave via a live `list_network_requests` trace; check whether clearing `localStorage` changes the repro rate (implicates the persisted-store restore).

---

## 4. Issue 2 — Meta-parameter apply (two separate bugs on one button)

### 2a — "Rate limited — please try again in a few seconds" (HTTP 429)

**Diagnosis (High).** Canopy's **own** `RateLimiter` (`security.py:91-223`, 429 @ `:213-223`) via `SecurityMiddleware` (`middleware.py:70-150`), **60/min per client IP**; `/api/set_params` is **not** exempt (`canopy_constants.py:342-356`). The dashboard's own fast pollers (`/api/status` hit by ~4 handlers/sec; ~25 `/api/*` GET sites; intervals `canopy_constants.py:212-213`) drain the single shared per-IP bucket within ~1-2s, so a click landing in a drained window 429s. Apply costs 2 requests (POST + verify GET) and retries ≤3× on timeout. Enabled in all deploys (`.env.prod:19-20`, `juniper-deploy` compose/Helm defaults). **Not cascor** — no 429 anywhere in the backend path. Partial mitigation exists (CAN-000 interval clamp `:2178-2228`) but the bucket can already be drained before the click.

**Resolve** — PR **`fix/canopy-ratelimit-internal-traffic`** (⚠ design decision — see §8): exempt internal same-origin calls (gate on the `internal_api_headers()` marker the dashboard already sends) **or** re-key the limiter by session/API-key instead of shared IP; add 429 backoff honoring the `Retry-After` header (handler currently gives up immediately, `:4926`); optionally consolidate the 4 per-tick `/api/status` polls.

### 2b — "Applied 19 of 27 … 8 not yet supported"

**Diagnosis (High).** Deterministic on *every* apply. `_apply_parameters_handler` builds a fixed **27-key** dict (`dashboard_manager.py:4853-4881`) regardless of what changed, one batched `POST /api/set_params`. The route (`main.py:2809-2944`) forwards only `nn_keys`/`cn_keys` (`:2837-2872`); the adapter (`cascor_service_adapter.py:761-846`) puts anything unmapped into `skipped` (`:778`). **7 of the 8 are flagged `_CANOPY_LOCAL_PARAMS`** (`:682-693`) — the code *knows* they're canopy-only ("should never be reported as skipped") but never subtracts them; the 8th, `cn_training_complete`, is a **status flag** that shouldn't be editable. **Hidden 3rd defect:** `nn_output_epochs`, `nn_optimizer_type`, `nn_activation_function_name` are silently dropped by `SetParamsRequest` (`main.py:2767-2806`) *before* the adapter (which *can* map them) — silent data loss, never surfaced. Message built at `:4920-4924`.

The 8 (alphabetical): `cn_training_complete` (status), `nn_dataset_elements`, `nn_dataset_noise` (dataset config), `nn_growth_preset_epochs`, `nn_growth_trigger`, `nn_multi_node_layers`, `nn_spiral_number`, `nn_spiral_rotations` (canopy-local).

**Resolve** — PR **`fix/canopy-apply-params-honesty`**:
1. Subtract `_CANOPY_LOCAL_PARAMS` from `skipped` in `apply_params` (collapses 8→~1).
2. Remove `cn_training_complete` from the editable set (read-only by nature).
3. Move dataset fields off `set_params` to the dataset surface (overlaps #4).
4. Add the 3 dropped fields to `SetParamsRequest` + the route allowlist (the adapter already maps them).
5. Compute an honest denominator.

**Tests / Verify.** Extend `tests/integration/test_apply_params_skipped_surfaced.py` to assert `_CANOPY_LOCAL_PARAMS` are **not** in `skipped`; the filter chain reproduces the exact "19 of 27 / 8" today, so post-fix assert "0 skipped on default apply".

**Phase 0.** Reproduce the 429 with `RATE_LIMIT_ENABLED=true` + a loop on `/api/status`; capture which limiter window the Apply lands in. Decide the limiter scope (exempt-internal vs re-key) — §8.

---

## 5. Issue 3 — Training stalls after ~1 iteration (three independent signals)

> **⚠ Phase 0 REFRAMED THIS ISSUE (2026-05-30) — see §8.1.** The live root cause is a **cascor dual-path / persistent-pool result-collection bug**: 40 candidates train but only the 2 remote-worker results are collected (the local in-process pool's ~38 results never reach the queue), so no best candidate is found and the network grows **0 hidden units** before reporting "Completed". The static "legit convergence" hypothesis below is **wrong**; the WS-idle-timeout and "Error"-from-poll-failure parts are real but **secondary/downstream** (the "Error" is dominated by the #2a 429). The original static diagnosis is retained below for context.

**Diagnosis (static, pre-Phase-0).**

* **"Completed" (~~legit~~ — actually 0-unit, see §8.1):** cascor cascade `grow_network` loop (`cascade_correlation.py:4240-4269`) **early-breaks** after ~1 growth iteration (residual `None` `:4244`, no best candidate `:4251`, or correlation below adaptive threshold `:4268`) → `fit()` returns → `monitored_fit` calls `mark_completed()` (`manager.py:1641`). Stays Completed for minutes (nothing running). **Whether this is genuine convergence or a mis-set `max_iterations`/threshold needs a live cascor run with the user's params.**
* **"WS: Reconnecting" (canopy latent bug, independent):** `/ws/training` has a 120s `idle_timeout` (`settings.py:102`; close at `main.py:538-540`) but **no server-side keepalive ping loop runs** (`websocket_manager.py:691-703` is a docstring-only Example) and the browser sends nothing unsolicited (`websocket_client.js`). After the stream goes quiet, the socket idles out → perpetual Connected→(120s)→Reconnecting flap, for *any* quiet period incl. a normal completion. The badge is driven **solely** by the browser WS flags (`connection_indicator.py:53-84`) — **not** `/api/status` freshness (corrects a prior-session memory).
* **"Error" (separate, later):** canopy's `GET /api/status` poll returns non-200 / throws (`dashboard_manager.py:4185,4198`) — cascor unreachable/crash, a self-401 if `CANOPY_API_KEY` is set (`internal_api.py:62-73`), or a >1s timeout (`FAST_API_TIMEOUT_SECONDS`). Needs live log capture to pin which.

**Resolve** — three PRs:
* **`fix/cascor-completion-reason`** (cascor): log *which* break fired at INFO; surface `completion_reason` in `get_status()` (`manager.py:2236-2256`) so canopy can distinguish converged vs stalled; review the adaptive threshold + default `max_iterations`.
* **`fix/canopy-ws-keepalive`** (canopy, standalone, high-confidence): start a real keepalive `asyncio.create_task` in the lifespan (interval 30s < 120s) — or raise/disable `idle_timeout` for `/ws/training`.
* **`fix/canopy-status-error-diagnosability`** (canopy): distinguish 401 vs 5xx vs timeout; render "Backend Unreachable" vs generic "Error"; handle the circuit-open 200 (`adapter:1264-1272`) explicitly instead of as "Stopped".

**Phase 0 live-confirm recipe.** Reproduce in **service mode** (demo cannot exhibit "Error"/"Reconnecting"). Watch: cascor log for the `grow_network` break reason + `mark_completed`; canopy `system.log` for `WebSocket idle timeout (120s)` ~2 min post-completion; the exception at the instant "Error" appears; `curl localhost:8201/v1/health` + `/v1/training/status` to tell cascor-crash from canopy self-call. Also test the #327/#328/#329 regression suspects: confirm the adapter still reaches cascor's status/metrics endpoints after the `/v1`-prefix strip, and the control-stream supervisor connects with the new `cascor_ws_origin`.

### 5.1 Confirmed root cause + revised fix (2026-05-30 read-only deep dive)

Verified firsthand in `cascade_correlation.py` + `parallelism/task_distributor.py`. **Two compounding defects** make training grow 0 units; BOTH need fixing.

**Defect 1 — collection timeout shorter than candidate training time (affects local single-path AND dual-path; likely PRIMARY).** `_collect_training_results` has a hardcoded `queue_timeout = 60.0` (`cascade_correlation.py:2595`; loop `:2624-2627`) and is called with the default at `:2403`. For a 40-candidate pool whose round takes ~2m18s (live log), the local collector hits its 60s deadline having drained ~0 results, then returns empty. Evidence: the ~60s gap between "Persistent pool created with 15 workers" (03:17:30) and "Dispatching 2 tasks to remote workers" (03:18:30) matches the 60s deadline; the round's logged `Training duration: 0:02:18` >> 60s. ⇒ Even a **local-only** run would lose results (it would log "expected 40, got 0"); the live "got 2" are only the remote results. Confirm via a DEBUG rerun showing `collected=0` at the deadline.

**Defect 2 — dual-path remote-fallback recreates the local pool mid-iteration (dual-path-specific; seals the loss).** `distribute_and_collect` runs local then remote (`task_distributor.py:104-106`); `_execute_remote_with_fallback` retries incomplete/`success=False` remote results via `retry_fn` = `local_fn` (`:196`, `:219`). That retry re-enters `_execute_parallel_training` with a tiny batch → `num_workers = max(1, min(process_count, len(tasks)))` (`cascade_correlation.py:2450`) → `_ensure_worker_pool(2)` sees `_persistent_pool_size (15) != 2` (`:3453`) → `_shutdown_worker_pool()` (`:3462`) SIGKILLs the 15 still-running workers and nulls `_persistent_result_queue` (`:3571-3575`) — discarding any late local results (the "Persistent pool created with 2 workers" line).

**Regression window:** dual-path machinery is recent (Phase 1b `8cde48f`, Phase 3 TaskDistributor `d94fef5`, both 2026-03-19); `tests/unit/test_task_distributor.py` mocks `local_fn`/`remote_fn` with complete in-memory lists, so neither defect is exercised. Defect 1 (60s timeout) predates dual-path but is newly fatal at this pool size.

**Revised fix (triad):**
1. *Stopgap (no code):* reduce `candidate_pool_size` / candidate epochs so a round finishes < 60s — partial only. Disabling remote workers avoids Defect 2 but NOT Defect 1.
2. *Correct:* (a) make `_collect_training_results` timeout adaptive (scale with candidate count × epochs, or a per-candidate budget) instead of hardcoded 60s; (b) make `_ensure_worker_pool` reentrancy-safe — never tear down a pool with undrained/in-flight work; size the pool to `_calculate_optimal_process_count()` not `min(_, len(tasks))` (`:2450`) and reuse a larger live pool when `num_workers <= alive_count` (`:3453`).
3. *Robust follow-up:* gate dual-path behind a workload threshold (`_split_tasks`, `task_distributor.py:122-140`) so a 2-remote-worker shape stays local; for this single-node deploy dual-path is net-negative.

Tests must drive the REAL `_execute_parallel_training`/`_ensure_worker_pool` (not mocked) with slow candidates + a fake coordinator returning a `success=False` result; assert hidden units grow > 0 and no second `_ensure_worker_pool(smaller)` within one `train_candidates`.

---

## 6. Issue 4 — Modified dataset never trains

**Diagnosis.**
* **Break #2 (real backend — the user's repro, High):** `apply_dataset` (`dashboard_manager.py:3461-3499`) drops `None` values (`:3484`); numeric inputs commit as `null` (Dash/React quirk) → `n_samples`/`noise` lost; only the dropdown `dataset_type` survives. **Apply-Dataset has no force-blur** (force-blur targets `apply-params-button` only, `:1983-2002`). On the real backend a *type* change does correctly cold-swap; element/noise edits silently don't.
* **Break #4 (real backend, conditional):** cascor `_reload_dataset` (`manager.py:2910+`) hard-requires `dataset_type` (`RuntimeError` otherwise); if the None-strip ever removes it, start fails or restages the default type while ignoring numeric deltas; the pending banner persists because cascor leaves `_pending_dataset_config` in place on failure.
* **Break #1 (demo only — latent, NOT the user's repro):** demo `start()` (`demo_mode.py:1441-1530`) never reads `_pending_dataset_config` written by `stage_dataset` (`:2065-2082`) — structurally inert in demo. Fix for parity, but de-prioritized given the deployed-stack context.
* cascor cold-swap wiring (`manager.py:2031-2092` consume `_pending_dataset_config` @ `:2090-2092` + `_reload_dataset`) is **correct**. The break is canopy-side.

**Resolve** — PR **`fix/canopy-dataset-apply-numeric-commit`** (shares the force-blur fix with #2): extend the force-blur clientside callback to `apply-dataset-button` (and the Live-Switch accept buttons); in `apply_dataset`, never strip `dataset_type` and coerce/keep numeric values rather than dropping `None`; surface a per-field "not committed" indicator (old #2 Option D). Optional follow-up PR **`fix/canopy-demo-staged-dataset`** for demo parity (Break #1). Optional UX PR to disambiguate the two dataset UIs.

**Tests / Verify.** Real-backend (`requires_cascor`) test: stage `dataset_type=moons, n_samples=300, noise=0.2` → start → assert cascor `pending_dataset` clears and dims/sample-count change. Adapter contract: assert `apply_dataset` payload still contains `dataset_type` when numeric fields are `null`, and force-blur Output lists `apply-dataset-button`. Demo unit test for Break #1 if that follow-up is taken.

---

## 7. Execution plan — worktrees, branches, PR map

**Worktrees** (centralized `…/Juniper/worktrees/`, per ecosystem convention). This effort's home base is the branch/worktree at the top of this doc (holds this plan + Phase 0 notes). Each Phase 1 fix gets its **own** branch off fresh `origin/main` and its own worktree (Paul's per-defect-PR convention). A cascor worktree for the #3 cascor work.

**PR map** (all independently shippable; → = shares code / verify-after):

```
Phase 1 (canopy, demo-testable, no live cascor):
  PR-A  fix/canopy-tab-feedback-loop            (#1)
  PR-B  fix/canopy-apply-params-honesty         (#2b)              → PR-D (dataset reclassification)
  PR-C  fix/canopy-ws-keepalive                 (#3 Reconnecting)
  PR-D  fix/canopy-dataset-apply-numeric-commit (#4 + #2 force-blur)
Phase 2 (live / cross-repo):
  PR-E  fix/cascor-completion-reason            (#3, cascor; needs live run)
  PR-F  fix/canopy-status-error-diagnosability  (#3 Error UX)
  PR-G  fix/canopy-ratelimit-internal-traffic   (#2a; verify on deploy stack)  [design decision first]
  (optional) fix/canopy-demo-staged-dataset     (#4 demo parity)
```

**Sequencing rationale.** PR-D closes #4 and the unfixed half of #2; PR-B references PR-D for the dataset reclassification. PR-C is fully standalone. PR-E/PR-G need the live stack. Merge order within Phase 1 is flexible; recommend A, C first (zero cross-deps), then D, then B.

**Open design decisions — RESOLVED 2026-05-30 (Paul, Phase 1 kickoff):**
1. **#2a limiter scope** — ✅ **Re-key the limiter by session/API-key (not per-IP)** *and* **honor the `Retry-After` header** with backoff in the apply handler (`main.py:4926`). (Chosen: options 2 + 3 — full fix, not the minimal exempt-internal.)
2. **#2b/#4 dataset fields** — ✅ **Relocate `nn_dataset_*` entirely to the dataset surface** (`/api/stage_dataset`); `set_params` no longer carries or reports them as skipped. (`_DATASET_PARAM_MAP` is the intended channel.)
3. **#1 tab persistence** — ✅ **Keep `layout-state-store`, delete the legacy localStorage pair** (`:2070`/`:2085`); equality-guard Reader B (`:2270`).
4. **Sequencing** — ✅ **Canopy Phase-1 fixes first**; the stack-mutating live-verify of cascor #315 runs as a later focused pass.

---

## 8. Phase 0 — reproduce & instrument (NEXT)

Goal: turn the static hypotheses into observed facts on the deployed stack before writing fixes, and produce baseline evidence each fix can be measured against.

1. **Stand up the stack** via juniper-deploy using the local-secrets `--env-file` pattern (point compose secrets at populated `secrets/`, not `secrets.example/`). **Check `juniper-cascor` image age first** (stale-image footgun) — rebuild `juniper-cascor`/`juniper-data` if older than the current `main`.
2. **Confirm real-backend mode**: canopy startup log shows `backend_type == "service"` (not silent demo fallback).
3. **Per-issue capture:**
   * **#1**: browser DevTools → click Snapshots→Dataset, record `_dash-update-component` POST stream (network trace) showing the `active_tab`/`layout-state-store` oscillation; note repro rate with/without cleared localStorage.
   * **#2a**: watch `/api/*` GET volume vs the 60/min budget; reproduce the 429 on Apply; capture the limiter `Retry-After`.
   * **#2b**: confirm the exact "19 of 27 / 8" toast (already reproduced via set-math) on a live apply.
   * **#3**: run training; capture the cascor `grow_network` break reason, `mark_completed`, the canopy `WebSocket idle timeout (120s)` line, the `/api/status` status codes over time, and the exception at the "Error" flip; `curl` cascor health/status at that instant.
   * **#4**: stage a numeric-only dataset change → start; confirm the staged payload dropped `n_samples`/`noise`; then stage a *type* change and confirm it does swap.
4. **Regression-suspect check (#3/#4):** verify #327/#328/#329 didn't break the adapter's cascor reachability (post-`/v1`-strip paths) or the control-stream origin handshake.
5. **Record findings** back into this doc (§3–6 "Phase 0 confirmed:" notes) so Phase 1 is evidence-driven and objectively evaluable.

### 8.1 Phase 0 — Confirmed findings (2026-05-30, live deployed stack)

Executed read-only against the running stack (all 9 containers healthy, ~17h uptime). Image build times: **canopy 2026-05-29 20:03**, **cascor 2026-05-29 17:08**, **data 2026-05-29 17:06**, **cascor-worker 2026-05-28 19:16** (a day older than cascor — rebuild for hygiene, but see #3: the lost results are the *local* pool, a cascor-side bug, not the remote path).

**#3 — REFRAMED (headline). Primary cause is a cascor dual-path / persistent-pool result-collection bug, NOT benign convergence.** Exactly one training run in 17h (the user's). cascor log sequence:

- `_ensure_worker_pool: Persistent pool created with 15 workers` → 40 candidate units train (correlations computed, candidate index ≥38).
- `_collect_training_results: Result queue empty, continuing` ×~10 (local result queue never fills).
- `_dispatch_to_remote_workers: Dispatching 2 tasks to remote workers`.
- `_ensure_worker_pool: Persistent pool created with 2 workers` (pool **recreated** mid-run — suspicious).
- `_process_training_results: Mismatch in results count: expected 40, got 2`.
- `grow_network: ... best candidate is None, stopping growth` → `Finished training after 0 iterations. Total hidden units: 0` → `fit: Training completed` → `State transition: Started -> Completed`.

Interpretation: with `Remote worker coordinator set — dual-path dispatch enabled`, the 40 candidates split between a local in-process pool and remote workers. The **local pool's ~38 results never reach the collection queue** (only the 2 remote results aggregate) → no best candidate → **0 hidden units grown** → premature "Completed". The double pool creation (15→2 workers) implicates a persistent-pool lifecycle / SharedMemory race. The remote path worked (2/2), so this is **not** the worker image skew — it's cascor-side. Implicated code: `juniper-cascor/src/cascade_correlation/cascade_correlation.py` — `_dispatch_to_remote_workers` (:1118), `_collect_training_results` (:2590), `_process_training_results` (:2074, the mismatch log), `_ensure_worker_pool` (:2451), stale-by-round discard (:2640). Fragile, actively-debugged concurrency (history: OPT-5 SharedMemory leak #61, RC-4 candidate race #203, CONC-10 coordinator lock #145). ⇒ **#3's real fix is a cascor concurrency fix**; the canopy WS-keepalive and Error-UX fixes are valid *secondary* work, and the cascor `completion_reason` surfacing makes the stall visible but does not fix it.

**#2a — CONFIRMED live.** Dozens of `frontend.dashboard_manager: Status API returned 429` (bursty, ~every 6s during active use). The dashboard self-throttles via canopy's own per-IP limiter, exactly as diagnosed. **This 429 is also the dominant source of #3's "Error" label** — a 429 on `/api/status` is non-200, which the status bar renders as "Error". So #2a and #3-"Error" share one root.

**#2 (apply) live signal.** Repeated `cascor_service_adapter: WS set_params failed, falling back to REST for hot params` — the WebSocket `set_params` control path fails and falls back to REST (which can then hit the 429). Possible link to the #328 `cascor_ws_origin` change; investigate during the #2 fix.

**Auth.** cascor `/v1/training/status` requires `X-API-Key` (health open, reports `0.5.0 ok`). canopy self-calls depend on `internal_api_headers()`; a key gap would 401→"Error", but observed "Error" is dominated by the 429, not 401.

**#1 / #4** are browser-interaction bugs not visible in server logs — defer to an interactive Phase 0 (drive the UI) or validate via each fix's tests.

**Net re-prioritization:** #3's primary (cascor result-collection) is the **highest-severity** issue — training currently produces a 0-unit network every run — and is a **separate cascor track** needing its own worktree + design pass (Paul's design-first / triad pattern). The canopy Phase-1 wins (#1, #2b, #4-numeric, #3-WS-keepalive, #2a-ratelimit) are unchanged and still valuable.

---

## 9. Testing strategy & constraints

* **Known harness limitation:** Playwright cannot drive Dash `dbc.Input(type=number)` (State stays `null`). UI tests must POST `/api/set_params` & `/api/stage_dataset` directly and verify via `/api/state` & `/api/dataset`. The tab loop (#1) is clientside-only — needs `dash[testing]`/`pytest-dash` or manual browser. The UI subsuite is split out via `--ignore=src/tests/ui` (loop-leak fix).
* Lean on **source-introspection unit tests** (the repo's existing pattern at `test_dashboard_manager.py:585-613`, `test_param_map_completeness.py`) + **direct-API integration tests**.
* Each PR adds regression coverage per canopy's "no PR without tests" rule and a CHANGELOG "Fixed" entry.

## 10. Documentation & memory plan

* This doc is the living tracker (see §11). On each PR: CHANGELOG "Fixed" + `notes/fixes/` update; `JR-CANOPY-*` refs in PR descriptions.
* Memory: the juniper-ml session memory `project_canopy_ws_badge_red_herring_2026-05-10` has been amended (2026-05-30) — the WS badge is now browser-WS-flag-driven, not `/api/status`-freshness-driven; idle-timeout is the proximate "Reconnecting" cause; "Error" remains the `/api/status`-downstream signal.

## 11. Status tracker (living)

| Workstream | PR branch | Status | Owner | Notes |
|---|---|---|---|---|
| Tracking doc (this file) | `fix/frontend-regressions-2026-05-30` | **In progress** | — | This PR. |
| Phase 0 reproduce & instrument | (same) | **Done (log pass)** | — | §8.1 — live evidence captured; #1/#4 still need interactive browser repro. |
| #1 tab feedback loop | `fix/canopy-tab-feedback-loop` | Planned | — | §3. |
| #2b apply-params honesty | `fix/canopy-apply-params-honesty` | Planned | — | §4. |
| #3 WS keepalive | `fix/canopy-ws-keepalive` | Planned | — | §5. Standalone. |
| #4 dataset numeric commit (+#2 force-blur) | `fix/canopy-dataset-apply-numeric-commit` | Planned | — | §6. |
| **#3 cascor result-collection (PRIMARY)** | `fix/candidate-result-collection` (cascor) | **PR #315 open — CI green; live rerun pending** | — | §5.1. **TWO defects fixed:** inactivity collection deadline + worker-liveness early-exit (Defect 1); `_ensure_worker_pool` reentrancy/reuse (Defect 2). 7 regression tests added. Pushed @ `4fa606d` (Black-formatting CI fix folded into the commit via amend). |
| #3 cascor completion-reason (surfacing) | `fix/cascor-completion-reason` | Planned | — | §5. Makes the stall visible; complements the primary fix. |
| #3 status "Error" UX | `fix/canopy-status-error-diagnosability` | Planned | — | §5. |
| #2a rate-limit scope | `fix/canopy-ratelimit-rekey-session` | Planned — design resolved | — | §4/§7. Re-key limiter by session/API-key (not per-IP) + honor `Retry-After` backoff. |
| #4 demo parity (optional) | `fix/canopy-demo-staged-dataset` | Backlog | — | §6 Break #1. |

---

## Appendix A — Investigation evidence (static analysis, 2026-05-30)

Four parallel subagents over canopy `d1ad3c5` / cascor `2d4a7dd`. Condensed file:line evidence retained for whoever executes (possibly a fresh thread per the handoff protocol). Full per-issue anchors are inline in §3–6. Highlights not repeated above:

* **#2b set-math reproduction:** replaying handler 27-key → `SetParamsRequest` fields → route `nn_keys`/`cn_keys` → `_CANOPY_TO_CASCOR_PARAM_MAP` reproduces the exact "Applied 19 of 27 … 8 not yet supported: cn_training_complete, nn_dataset_elements, nn_dataset_noise, nn_growth_preset_epochs, nn_growth_trigger…" byte-for-byte (alpha sort + 5-item preview + ellipsis).
* **#3 badge path (memory correction):** `ws-connection-status` store written exclusively by clientside `peekConnectionStatus()` ← `window._juniperWsDrain._connectionStatus` ← `websocket_client.js:_notifyConnectionStatus()`. No `/api/status` input, no staleness timer in the badge path.
* **#4 dataset paths:** sidebar "Apply Dataset" (cold-swap, `/api/stage_dataset`) vs Dataset-Plotter "Generate" modal (`/api/dataset/generate`, **400 on real backend** — demo only). Only the latter reaches `regenerate_dataset`.
* **cascor lineage:** `#240` `normalise _pause_event in reset()` + `#244` pause/stop interrupt (old #5, fixed); `#241/#243` candidate-pool PATCH (old #1 contract); P2-1a…P2-7 (`#245`–`#259`) live dataset swap.
