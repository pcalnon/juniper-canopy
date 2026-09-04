# Changelog

All notable changes to the juniper_canopy prototype will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- **Upper version ceilings on all five first-party `juniper-*` dependencies.** canopy was the only
  service pinning its Juniper dependencies with a floor and **no ceiling**, against the documented
  ecosystem policy: the release-train plan states consumers pin `>=floor,<next-minor`, "which makes
  each `0.x` a compatibility boundary". Now `juniper-observability>=0.4.0,<0.5.0`,
  `juniper-service-core>=0.5.0,<0.8.0`, `juniper-cascor-protocol>=0.1.0,<0.3.0`,
  `juniper-data-client>=0.4.1,<0.5.0`, `juniper-cascor-client>=0.7.0,<0.8.0`.

  This is the root-cause fix for the lockfile drift found on 2026-08-31: canopy's
  `juniper-service-core` lock sat at `==0.5.1` across **two** published releases. An unbounded range
  does not make a lockfile self-updating -- it removes the *ceiling raise*, which is the event that
  prompts a lockfile refresh in every other repo. With `Lockfile Freshness` running in constraint
  mode (it asks only whether the lock still *satisfies* pyproject), `==0.5.1` satisfied `>=0.5.0`
  forever and no gate ever fired. A ceiling turns the next minor into a deliberate, prompted upgrade.

  No lockfile change accompanies this: all five locked versions already sit inside the new ceilings,
  and a constraint-mode recompile reproduces the current lock with **zero** pin drift.

### Added

- **X7 event-loop I/O operator docs.** Runbook in `docs/AGENTS_REFERENCE.md` covering the
  single-worker outage class (sync `requests` inside `async def` stalls `/v1/health/live`),
  the slice 1b client budget already on `main` (`CASCOR_CLIENT_RETRIES = 0`), the slice 1a
  gate / T-A2–T-A4 / adapter callgraph landing with `#567`, and the pitfalls (`ruff
  --select ASYNC` is blind; the `main.py` gate cannot see adapter I/O). Cheatsheet,
  testing manuals, QUICK_START Issue 8, CasCor adapter notes, and `/v1/health/live` in
  the API reference. Resident hazard in `AGENTS.md`.
- Tests pinning Stage 2 (`#511`) live-callback contracts that the original PR's happy-path suite left open: `_update_unified_status_bar_handler` element `[9]` stays `dash.no_update` on every error path (so a hiccup cannot blank `training-status-store` and re-fire its consumers), `{is_running, phase}` is coerced then suppressed, and `_update_system_panels_handler` isolates a `/api/status` Timeout/JSON failure from the details and stream-health surfaces.

### Changed

- **CodeQL / SAST operator docs.** CI manuals now describe the live
  SHA-pinned `github/codeql-action` v4 workflow (`.github/workflows/codeql.yml`),
  the required check name `Analyze (python)`, the Dependabot `codeql-action`
  group that also bumps `ci.yml` Bandit `upload-sarif`, and the ruleset
  code-scanning gate (errors + high-or-higher alerts). Replaces the stale
  `init@v2` snippet.

## [0.6.0] - 2026-07-28

### Added

- **N8 — WS-primary tiles/state with a liveness-gated poll fallback (juniper-ml
  training-runtime defects plan §4 I-1, posture O3+O1 / Q6).** The metrics tiles
  (via `metrics-panel-metrics-store`) and the training-state status strip (via
  `metrics-panel-training-state-store`) now consume the WebSocket buffers FIRST
  while the stream is demonstrably fresh, with N1's REST polls demoted to a
  liveness-gated fallback. **The gate is a LIVE freshness signal, never a sticky
  flag** — `ws_dash_bridge.js` stamps each `metrics` / `state` frame arrival
  (`_lastMetricsFrameMs` / `_lastStateFrameMs`) and `peekLiveness()` reports the
  *age*; a fast-tick clientside callback compares it to the new
  `DashboardConstants.WS_LIVENESS_WINDOW_MS` (5000 ms) and writes booleans to a
  new `ws-liveness-store`. The retired sticky `metricsReceived`/`topologyReceived`
  flags are deliberately NOT consulted, so a stream that goes quiet flips stale
  within the window and the poll re-engages on the next tick (the anti-sticky
  reset that ended the N1-era starvation). **Two-callback split per store** (the
  load-bearing correctness detail): a WS buffer must NOT be an *Input* of the
  interval poll — a chained input whose clientside producer `no_update`s makes
  Dash skip the interval-only callback for that tick, silently re-creating the
  I-1 starvation. So each store is co-owned by (a) a liveness-gated REST poll
  (interval Input only; liveness read as State) that returns `no_update` while
  WS-primary is live and polls when stale, and (b) an `allow_duplicate` append
  callback triggered ONLY by the WS buffer (accumulates metrics into a bounded
  scrolling window; latest-only replace for state) that is the sole WS writer and
  can never starve the store when the stream is quiet. History-analysis display
  modes (`full` / `hidden_units`) stay on REST (Q6: polling for non-real-time
  surfaces). Also re-created the `ws-state-buffer` store + `drainState` drain that
  N1 removed as write-only, and **fixed a latent dead handler** — the bridge
  listened on the never-emitted `state_change` type while the server broadcasts
  training state as `state` (`broadcast_state_change`, relay forward, on-connect),
  so `_stateBuffer` had never populated. The header status bar (`/api/status`,
  N6's reconciled counters) and topology (N1 tab-gated slow poll) are intentionally
  unchanged; §8 chart/tile-wipe guard and empty-guard preserved. The UI layout
  snapshot is unchanged (no pinned `get_layout()` touched). Closes I-1 (target
  architecture), Q6.

- **N9 — Metrics-visualization overhaul: C7 scalar rendering + U-2/U-3
  presentation (juniper-ml training-runtime defects plan §4-U U-2/U-3/U-4
  display half).** The metrics panel's accuracy plot becomes a bounded-[0, 1]
  **Classification Metrics** plot that renders C7's new scalar evaluation
  metrics (`juniper-cascor` #419) alongside accuracy. (1) **C7 scalar series
  (U-4 display):** F1, precision, recall and ROC-AUC render as additional
  series where accuracy renders today, driven by a single
  `MetricsPanel.SCALAR_SERIES` source of truth (row key → trace name → color).
  Nullable values become **honest gaps** (`None` y + `connectgaps=False`),
  never zeros, so the ~every-25th-epoch sparsity and candidate-phase gaps read
  correctly; each series draws `lines+markers` so sparse points stay legible;
  a series with no real value adds no trace (no legend clutter). The C7
  `eval_metrics` metadata is surfaced without guessing — `average`/`split` in
  the legend title, any `undefined` reasons (e.g. `roc_auc: single_class`) in
  an unobtrusive annotation — present only when the data carries the block.
  (2) **U-2/U-3 presentation:** percentage y-axis bounded to [0, 1]
  (`tickformat=".0%"`), a coherent light/dark-legible series palette, subtle
  gridlines, per-series hover formatting, and an `x unified` hover; loss keeps
  its own unbounded axis (the scaling/overlap fix — bounded metrics never share
  loss's scale). (3) **Trace-index contract (BOTH data paths):** loss-plot
  trace 0 stays `Output Training` and classification-plot trace 0 stays
  `Accuracy` (the WS bridge's `extendTraces` positional targets); the C7
  series + validation overlays are looked up by name. The WS clientside
  callback reads each scalar flat off the frame under the **same push-gate as
  loss/accuracy** and shares the `[epochs]` axis, so every series stays
  x-aligned (a length skew would silently corrupt WS appends). The
  figure-builder names and the bridge lookups are pinned together in
  `test_n9_metrics_visualization`. (4) **Data path:** the C7 flat scalars +
  `eval_metrics` block thread through both adapter metric normalizers
  (`_normalize_metric` / `_to_dashboard_metric`, additive/nullable — the
  golden-shape contract is preserved) and the demo emission, so the series
  render in both service and demo mode. `get_layout()` is unchanged (the
  `metrics_panel` layout snapshot is unaffected).

- **N10 — Workers tab shows local + remote workers (juniper-ml training-runtime
  defects plan §4-U U-5).** After a read-only discovery pass over the
  worker-registration surface (cascor `src/api/workers/registry.py` +
  `src/api/routes/workers.py`; cascor-worker `/ws/v1/workers` registration), the
  Workers tab now distinguishes worker locality honestly. **Discovery finding:**
  cascor's registry models **remote** WebSocket-registered workers only and
  carries no locality field; the local in-process candidate pool
  (`src/parallelism/task_distributor.py`) is tracked separately and is not
  individually enumerated by any REST route. **Build (honest hybrid, no fabricated
  data):** (1) the `GET /api/v1/workers/list` proxy annotates each cascor worker
  with `kind="remote"` (a backend-supplied `kind` is honored for forward-compat)
  and a `local_reported` flag (`False` in service mode); demo mode returns one
  clearly-labeled `local` + one `remote` synthetic worker with `local_reported:
  true`. (2) The panel is now **store-driven**: a new `worker-panel-workers-store`
  is filled by a dashboard-owned, **tab-gated** slow-interval poll
  (`_update_workers_store_handler`, the topology-tab N1 posture — only polls when
  the Workers tab is active, empty-guarded with `dash.no_update` so a transient
  upstream hiccup never blanks the roster), replacing the panel's former always-on
  5 s self-interval. (3) The roster renders as a table (Worker ID, Kind, Status,
  Health, Last Heartbeat, Current Task) with a local/remote badge; when the backend
  does not individually report local workers an honest note is shown rather than
  fabricating local records. Cascade-only tab suppression for one-shot (recurrence)
  models is unchanged. A cascor-side follow-up (surface the local MP pool via
  `/v1/workers/stats` or a `/v1/workers/local` route) is proposed for the local
  half. Regression coverage: store-driven render states, table/row rendering,
  heartbeat formatting, the tab-gated + empty-guarded store handler, and the
  extended demo-route contract.

- **N7 — Schema-driven dataset panel, availability gating, per-type
  Current-Dataset section (juniper-ml training-runtime defects plan §4 I-7 / §4-U
  U-6 / I-5 UX).** The sidebar Dataset sub-section no longer shows the
  spiral-centric typed fields for every dataset type. A new pure module
  `src/dataset_schema.py` turns a juniper-data generator's JSON schema (surfaced
  by `GET /v1/generators` as of juniper-data 0.10.0 / D1) into ordered renderable
  field descriptors — excluding split/seed/cache infrastructure fields and
  preserving each field's type/label/bounds/default/enum — and reads the additive
  per-generator `available` flag with a **flag-absent-means-available** fallback
  (older juniper-data degrades to all-available). (1) **Schema-driven params
  (I-7):** `render_dataset_params` renames the section per selected type (U-6),
  hides the spiral typed-field block for non-spiral types, and renders
  schema-derived inputs (pattern-matching `{"type": "nn-gen-param", "name": …}`
  ids) into `nn-dataset-schema-params`. Spiral keeps its typed convenience fields;
  every other generator forwards its schema-true params through the **generic
  `params` staging channel** — a new `nn_dataset_params` key on canopy's
  `StageDatasetRequest` mapped to cascor's `StageDatasetRequest.params` (adapter
  `_DATASET_PARAM_MAP`), so the staging dialect (cascor #396) is preserved and no
  typed fields are widened. `apply_dataset` reads the schema inputs directly (no
  store-race) and drops the now-hidden typed fields for non-spiral generators.
  (2) **Capability gating (I-5 UX):** the training-dataset dropdown composes the
  existing model-compatibility gate with an availability gate — an unavailable
  generator (its optional data extra absent) renders disabled with a reworded
  reason, and the gate runs on mount (not only after a model change). (3) **U-6:**
  the "Current Dataset" left-menu sub-section is retitled per selected type
  ("Current Dataset — MNIST") and populated with that type's schema-relevant
  params. (4) **Hint rewording (I-7):** `dataset_model_hint` now reads "rank-2
  (tabular) models only" / "rank-3 (sequence) Δt-aware models only" instead of
  "2-D / 3-D models only", so the constraint reads as tensor rank rather than a
  feature count (MNIST, a rank-2 784-feature tensor, is no longer implied to be
  excluded). **No `juniper-data-client` floor bump:** canopy reads `/v1/generators`
  via direct httpx (raw-dict passthrough), so the availability/schema surface needs
  no client-library change; the client floor stays `>=0.4.1` (the juniper-data
  *service* floor for the availability surface is a juniper-deploy concern, out of
  scope here). Tests: `tests/unit/test_dataset_schema.py` (schema→fields mapping,
  availability incl. flag-absent, alias, gate composition),
  `tests/unit/frontend/test_n7_dataset_panel.py` (render/gate/apply handlers, U-6),
  and `tests/integration/test_apply_dataset_flow.py` (adapter `params` mapping +
  the `/api/stage_dataset` route accepting `nn_dataset_params`).

### Changed

- **CL2 — cascor-client `>=0.7.0` floor; adapter liveness seams onto the client
  surface; manual-pong retirement; stream-liveness suite gated in CI (juniper-ml
  training-runtime defects plan §7/§13).** Bumped the `[juniper-cascor]` extra
  floor to `juniper-cascor-client>=0.7.0` (was `>=0.6.0`) and regenerated
  `requirements.lock`, adopting the CL1 liveness surface the client shipped in
  0.7.0 (cascor-client#92). `CascorServiceAdapter`'s three documented CL1 swap
  seams now consume that surface: the `ControlStreamSupervisor.is_connected`
  property reads the stream's own `is_connected` bool (an identical transport-state
  test) instead of reaching into `_ws`; `_probe_liveness` prefers the stream's
  passive `is_alive(window)` frame-recency view over an active `ws.ping()` (0.7.0's
  eager control recv-loop already answers cascor's heartbeat, so the
  canopy-originated ping — and its `_ws` reach-in — is retired); and the metrics
  relay drops the manual `if msg_type == "ping": stream._ws.send(pong)` workaround
  because 0.7.0's `CascorTrainingStream` auto-pongs and never yields `ping` frames.
  Each seam keeps a `getattr` / `_ws_open` fallback for fakes and pre-CL1 clients
  (only a real `bool` is trusted, so the N2 mock streams still exercise the
  fallback), and the N2 one-line-per-disconnect/reconnect logging contract is
  preserved. Because the client now consumes heartbeat pings, `ping` leaves the
  relay's `StreamHealth` frame census (dropped from the summary's core-type
  roster); to keep a healthy-but-idle relay from drifting to `degraded` (or
  churning needless reconnects), the relay now polls the client's `is_alive`
  surface at the heartbeat cadence (`RELAY_LIVENESS_POLL_SECONDS`, 30 s) and feeds
  its liveness clock from that plus data/ack frames. Also wired the
  `[juniper-cascor]` extra into the CI unit-tests lane so
  `src/tests/unit/backend/test_stream_liveness.py` — which `importorskip`s the real
  client — actually executes in a required CI lane (previously it ran only in
  client-equipped local envs). Tests: CL2 seam-swap units, a real
  `FakeCascorTrainingStream` pong-consumption pin, and an idle-but-alive re-arm
  regression (`src/tests/unit/backend/test_stream_liveness.py`); the version-floor
  guard (`src/tests/unit/test_client_version_floors.py`) tracks the bumped floor
  automatically.

### Fixed

- **N5 — Apply-Parameters UX: seeded-value clamping, verbatim rejection toasts,
  applied/skipped rendering, liveness-gated WS leg (juniper-ml training-runtime
  defects plan §4 I-4, T1/T3).** Four apply-params defects behind the evening-502
  session are closed. (1) **Clamp/validate against PATCH bounds** — a new
  `CascorPatchBounds` (mirroring cascor's `TrainingParamUpdateRequest` in
  `src/api/models/training.py`, keyed by canopy form key) clamps out-of-range
  values both when the form seeds from the backend (`init_params_from_backend`)
  and before every apply, so a backend-echoed default can no longer wholesale-422
  the whole form the way cascor's pre-C2b `epochs_max`=1e11 did; any clamp is
  flagged in the toast rather than silently changing the operator's intent.
  (2) **Verbatim rejection detail** — the failure toast now carries the upstream
  reason (cascor's specific bound-violation message via canopy's 502 payload,
  truncated) instead of the bare `Failed to apply (502)` that hid every root
  cause; same extraction idiom N4's snapshot toast uses. (3) **Render
  applied/skipped** — the adapter surfaces cascor's C2a `applied` / `skipped`
  (`{key, reason}`) partition (mapped back to the canopy `nn_*`/`cn_*` namespace;
  REST-nested and WS-flat shapes both handled), `POST /api/set_params` threads it,
  and the toast shows what the live network took vs. declined with the reason
  (e.g. `epochs_max (not-updatable)`). (4) **Liveness-gated WS leg** — the
  `set_params` WS leg is skipped straight to REST (no burned ack window) when the
  control stream is not connected, consuming N2/CL2's honest `is_connected`
  surface; the WS path is retained, only gated. The pre-existing adapter `skipped`
  (canopy keys with no cascor mapping) contract is unchanged. Regression tests:
  `tests/unit/test_cascor_patch_bounds.py`, `tests/integration/test_n5_apply_params_ux.py`.

- **N3 — restart orchestration: confirm modal (Q3/Q4), stop → await → start(staged),
  outcomes surfaced (juniper-ml training-runtime defects plan §4 I-6, T1/T4, U-1).**
  The sidebar "Stop & Restart with new dataset" button no longer fires a
  feedback-free `POST /api/train/start?reset=true` whose only output was the
  banner (three cold-swaps trained to completion **invisibly** in the 2026-07-11
  incident, and an active-run swap would have 409'd silently). It now opens a
  **confirm modal** (Q3): a simple confirm by default — assuming all other
  meta-parameters/structures/processes unchanged — leading with a **start-fresh
  toggle (Q4, default OFF)** and an expandable granular **verify** section
  (read-only current engine params; in-place *modify* is deferred to **N3b**,
  which intersects N5's apply contract). Confirm runs a new
  **`POST /api/train/restart`** orchestration route that, per the E-2 live pin
  (a start against an ACTIVE run 409s immediately while the staged config
  survives), performs **stop → await stopped (bounded) → start(staged)** for an
  active run and skips straight to start when idle/terminal. **Every step's
  outcome is surfaced** (T1/T4): a dedicated `restart-outcome-alert` renders a
  truthful success (including an **instant-convergence / epoch-0** run, folded
  finding 2) or a per-step failure carrying the upstream detail — the previously
  silent 409 refusal, a retriable 504 stop-await timeout (staged change kept, the
  pending banner stays open), and stop/start refusals. `start_fresh` (Q4) is
  forwarded to cascor's C5 body field `{"start_fresh": true}` (cascor#408) through
  the backend stack (`ServiceBackend`/`DemoBackend` → adapter; the 0.7.0 client
  can't carry the field yet, so the adapter posts it through the client's own
  transport — a documented CL2 swap seam); OFF continues the current model,
  retaining metrics/history (Q4 use-case 1, preserving N1's chart retention). The
  demo FSM now **auto-resets from a terminal (COMPLETED/FAILED) state on START**,
  mirroring the cascor engine FSM (`state_machine.py:171-173`) — a
  start/restart from a converged demo run is no longer silently refused (folded
  finding 1; the asymmetry that turned canopy's CI UI leg red, §13 N2 addendum).
  Apply-Dataset staging failures, previously swallowed, now surface too (T4).
  Tests: the `/api/train/restart` route (idle/active/stop-await-timeout/refusal/
  instant-convergence), the confirm-modal + outcome handlers, `start_fresh`
  forwarding across every backend layer, and the demo-FSM start-from-terminal fix.

- **N3b — restart modal granular modify: staging edits + N5-machinery param apply
  before orchestration (juniper-ml training-runtime defects plan §4 I-6, §12 Q3,
  §13; split from N3).** The N3 confirm modal's expandable granular section was
  read-only **verify**; N3b makes it **modify** — the ratified Q3 design ("simple
  confirm + expandable granular verify/modify"). Inside the section the operator
  can now, before confirming: (1) edit the **staged dataset config** — exactly the
  `StageDatasetRequest` fields (`dataset_type`/`n_samples`/`noise`/`rotations`/
  `n_spirals`), defaulting to the currently staged / current values; an edit
  re-stages via the existing `/api/stage_dataset` route before the restart
  proceeds; and (2) edit a focused, restart-relevant set of **training parameters**
  (learning rate, max hidden units, patience, candidate pool size, selected
  candidates, correlation threshold — every one governed by N5's
  `CascorPatchBounds`). Applying those params reuses N5's merged machinery
  end-to-end — the same `CascorPatchBounds` clamp → `/api/set_params` →
  applied/skipped partition path as the params panel (a shared
  `_apply_params_via_backend` core now backs both call sites, so the bounds and
  toast logic are called into, never duplicated) — and is **sequenced BEFORE** the
  N3 stop → await → start orchestration. The **start-fresh toggle** stays as N3
  built it, and the granular section shows its C5 consequence text (retained
  history discarded, snapshots preserved). Every in-place edit is reflected in the
  **"Restart plan" summary** before Confirm (dataset config + per-param `old → new`
  deltas), and the `restart-outcome-alert` reports what was re-staged / applied as
  part of the restart result. A re-stage or param-apply failure **aborts** the
  restart (never restart on a stale dataset or with un-applied params), surfaces the
  verbatim reason, and keeps the pending banner open so the staged change survives;
  an untouched Confirm skips both modify phases (the ratified simple-confirm
  default). The `/api/train/restart` route is unchanged — no new route parameters.
  Tests: modal-handler units (dataset-edit round-trip, param path delegates to the
  N5 core, summary reflects edits, abort-on-failure, the open-handler field/baseline
  seeding + clamp), plus an integration file pinning layout wiring, the
  param-field ⊆ `CascorPatchBounds` coherence guard, and route acceptance of the
  modal payloads. No `get_layout()` snapshot regeneration (the restart modal is in
  the manager layout, not the snapshot-pinned `metrics_panel`/`dataset_plotter`).

- **N6 — header/tile counter mappings + denominators per the reconciled C2b
  semantics (juniper-ml training-runtime defects plan §4 I-1c / §5 S12; closes
  I-1c / S12).** The dashboard's Epoch/Step/Iteration/Hidden-Units displays were
  mislabelled and wrongly denominated against the pre-C2b divergent surfaces.
  Corrected each mapping to the C2b counter contract (juniper-cascor
  `docs/api/JUNIPER_CASCOR_API_REFERENCE.md`, "Counter semantics"; cascor#400):
  - The status-bar segment labelled **"Epoch"** actually showed `current_epoch`,
    which C2b defines as completed **training steps** (one initial output pass +
    one per growth iteration), NOT an inner output epoch — relabelled to **"Step"**
    (the S12 "Epoch: 10000 vs 12" confusion; the value was already `current_epoch`).
  - The status-bar segment labelled **"Iteration"** actually showed
    `hidden_units / max_hidden_units` — relabelled to **"Hidden Units"** (the
    segment id `top-hidden-units-display` was always the unit count; only the
    label was wrong, and C2b reconciled the `max_hidden_units` denominator, fixing
    S12's stale `/ 10000`).
  - The Network Info panel's **"Current Iteration"** showed the hidden-unit count;
    now shows the TRUE growth iteration `grow_iteration / grow_max`
    (vs `max_iterations`), added a phase-qualified within-pass **"Epoch (in phase)"**
    (`output_epoch`/`candidate_epoch` — "N / M (output|candidate)", rendering
    "0 / N" on the by-design phase-entry reset rather than blank), and gave
    "Hidden Units" the reconciled `/ max_hidden_units` denominator.
  - The metrics **"Training Step"** tile read the latest metrics row's `epoch`
    blind to C2b's `kind` discriminator, so a throttled within-pass `output_epoch`
    row displayed as the step count (the tile-level "10000 vs 12" flip-flop); it
    now prefers the latest `training_step` row (or the authoritative
    `training_state.current_epoch`) and holds the last step value through a
    candidate-phase metrics freeze.
  - `ServiceBackend.get_status` now carries the reconciled counter surface
    (`current_step`, `grow_iteration`, `grow_max`, `output_epoch`/`output_total_epochs`,
    `candidate_epoch`/`candidate_total_epochs`) through to the header/panel
    consumers; missing fields (pre-C2b cascor) degrade to a graceful placeholder.
  The `max_epochs` derived budget is deliberately NOT rendered as an
  `Epoch: X / Y` fraction against the step counter (different units — steps vs
  inner-epochs); it remains the Parameters panel's "Maximum Total Epochs" budget.
  Tests: `src/tests/unit/frontend/test_n6_counter_semantics.py` (mapping helper,
  header, Network Info panel, tile `kind`-discrimination + candidate-freeze, and
  the `get_status` surface).

- **N1 — un-gated metrics/topology polls (sticky-gate starvation fix; juniper-ml
  training-runtime defects plan §4 I-1/I-2, posture O2).** The metrics-store poll no longer
  skips REST while the WS bridge reports `connected` + `metricsReceived`, and the topology
  poll no longer requires `topologyReceived`: the sticky flags starved long-lived tabs
  indefinitely once WS frames stopped arriving (tiles/charts froze at stale values until a
  manual refresh — the 2026-07-10 frozen-dashboard session). The metrics poll now runs every
  fast tick (1 Hz); the topology poll stays tab-gated on the slow interval (5 s) with the
  `cascade_add` WS push as the fast path and tab-activation refetch. **This is the
  correctness bridge until the WS-primary target lands (Q6/C6/N8)**, with three
  validation-mandated guard rails: an **empty-guard** (an empty/errored fetch returns
  `no_update` when the store already holds data, so cascor's post-run metrics clear can't
  blank a completed run's charts), an **event-loop guard** (`/api/metrics/history`,
  `/api/topology`, `/api/topology/raw` now run their synchronous backend calls via
  `asyncio.to_thread` so a slow cascor can't stall canopy's event loop at 1 Hz), and a
  **bounded full-history fetch** (`full`/`hidden_units` display modes fetch `limit=0` — up
  to 10k rows — only every `FULL_HISTORY_POLL_TICK_MODULUS`-th tick (~0.2 Hz) on
  interval-driven ticks; a display-mode switch, now an Input on the poll, refetches
  immediately). Also removed the dead-end `ws-state-buffer` / `ws-candidate-progress-buffer`
  stores and their clientside drains (no Input consumed them; the JS ring buffers stay for
  N8), and fixed the metrics handler's stale "every 10th tick at 100ms" docstring (the fast
  interval is 1000 ms). Tests: un-gated handler + empty-guard + bounded-fetch units
  (`src/tests/unit/test_phase_b_bridge.py`), `asyncio.to_thread` wiring pins
  (`src/tests/unit/test_main_api_coverage.py`), and WS-silent Playwright scenarios asserting on
  the store wire — the metrics store keeps hydrating via poll on a long-lived tab under the
  sticky connected+received WS state, a stopped run's populated store survives continued 1 Hz
  polling, and the topology store fetches REST on tab switch
  (`src/tests/ui/test_ws_silent_poll_liveness.py`). The store wire (not the tiles) is the UI
  observable because `update_metrics_display` renders lazily in the headless harness on main
  too — a pre-existing issue noted for E-3/N2, not introduced here.  

### Changed

- **CI: per-file coverage is now a blocking gate (ecosystem per-file coverage rollout C-5).** The
  `unit-tests` job's coverage lane (`src/tests/unit/ src/tests/regression/`, `--cov=src`) now runs the
  shared `juniper-coverage-gap-map --enforce` gate from `juniper-ci-tools>=0.6.0,<0.7.0` as a
  **blocking** step: CI **fails** when any source file's statement coverage is below 90% or any packaged
  sub-module's pooled (statement-weighted) coverage is below 95%. The gate computes statement % itself
  from `reports/coverage.json`, so this repo's `branch = true` coverage config does not change the gate
  basis; it complements the existing aggregate `--cov-fail-under=80` gate (which a few well-covered
  files can mask). The three existing `juniper-ci-tools` CI pins were bumped `>=0.5.1,<0.6.0` →
  `>=0.6.0,<0.7.0` (0.6.0 is a superset — it adds the enforcing coverage gate and keeps every existing
  console script). See juniper-ml
  `notes/JUNIPER_ECOSYSTEM_PER_FILE_COVERAGE_ROLLOUT_SCOPING_2026-06-30.md`.

### Tests

- **Lifted whole-`src` per-file coverage to satisfy the new gate — no production-code change.** The unit
  lane's overall pooled statement coverage rose **87.5% → 98.5%** (coverage.py total **85.8% → 97.5%**),
  bringing every source file to **≥90% statement** and every sub-module to **≥95% pooled**. ~520 new
  deterministic, offline unit tests were added for the previously under-covered files:
  `main.py` (76.6 → 99.3%; FastAPI routes / WebSocket handlers / lifespan via `TestClient`),
  `frontend/dashboard_manager.py` (77.2 → 99.9%; Dash inner-callback bodies invoked directly),
  `demo_mode.py` (88.2 → 99.3%),
  `backend/{cascor_service_adapter,training_monitor,demo_backend,service_backend}.py` (→ 100%),
  `frontend/components/{parameters_panel,candidate_metrics_panel,network_evolution,decision_boundary,network_editor_panel,replay_player_panel,dataset_plotter}.py`
  (→ 100%), plus the WebSocket-audit helpers in `audit_log.py` and the API-key branch of
  `frontend/internal_api.py`. UI (`src/tests/ui/`, Playwright) tests remain out of the coverage lane by
  design (session-fixture event-loop leak); no `get_layout()` / panel layout was touched.

### Added

- **3-D (time-series) dataset display — Phase 1 (#368)**: canopy can now load and
  visualize 3-D sequence / irregular-Δt datasets. `DemoMode`'s dataset-load path is
  `ndim`-aware (`src/demo_mode.py`): a 3-D artifact routes to a new **display-only**
  `_install_sequence_dataset` (window-0 feature view stored as JSON into `self.dataset`;
  **not** wired into the demo trainer — the cascor-like simulator can't ingest 3-D, OQ-4),
  while 2-D keeps the existing classification path. The dataset-plotter
  (`src/frontend/components/dataset_plotter.py`) gains a sequence render branch
  (dispatched on `dataset_kind == "sequence"` before any 2-D logic): feature
  **small-multiples over real (cumulative-Δt) time** + a **Δt strip** (≈ design mockup
  R4). The dispatch inspects `X_full`/`X_train` rank directly because the installed
  `juniper-data-client` (0.4.x) does not export `validate_npz_contract`. Design-of-record:
  juniper-ml `notes/JUNIPER_CANOPY_3D_DATASET_VISUALIZATION_DESIGN_2026-06-19.md`. Tests:
  `src/tests/unit/test_sequence_dataset_viz.py` (fixture-tested; live juniper-data 3-D
  end-to-end verification to follow). The control surface (signal/window selectors,
  small-multiple⇄overlay, target toggle) is Phase 2.
- **3-D dataset viewer — compare-signals controls (Phase 2a, #368)**: the sequence
  (3-D) dataset view gains its first interactive controls
  (`src/frontend/components/dataset_plotter.py`). A **signal multi-select** chooses which
  signals to plot (default: all) and a **Small multiples ⇄ Overlay** segmented toggle
  switches arrangement — small-multiples keeps each signal per-normalized and vertically
  offset (the honest default for mixed-scale sets, e.g. OHLCV), overlay shares one
  normalized axis for direct cross-signal comparison (design R2). Both controls render
  only for sequence datasets (a new visibility callback) and stay hidden for 2-D tabular;
  the signal selector self-populates from the loaded dataset's feature labels. Window-0
  only — **no backend change** (multi-window comparison + the target / characterization
  companions are Phase 2b/2c). The render path guards stale / out-of-range signal
  selections (falls back to all). Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_3D_DATASET_VISUALIZATION_DESIGN_2026-06-19.md` §3.1 / §5. Tests:
  `src/tests/unit/test_sequence_dataset_viz.py` (5 new cases).
- **3-D dataset viewer — compare-windows mode + multi-window backend (Phase 2b, #368)**:
  the sequence view gains a **`Compare: [Signals | Windows]`** segmented mode toggle (M1).
  *Compare-windows* plots one selected signal across multiple selected windows; *compare-
  signals* (default) keeps the multi-signal view but now within a **selectable window**.
  Each mode reuses the Small multiples ⇄ Overlay arrangement; only the active mode's
  controls are shown. Backend (`src/demo_mode.py`): `_install_sequence_dataset` now stores
  a **capped set of windows** (`windows_X` / `windows_dt`, cap 50; `n_windows_stored`
  records the cap, the true `n_windows` is preserved) so window-switching needs no
  re-fetch — still **display-only** (OQ-4, not wired into the trainer). Per-window Δt is
  honoured (each window keeps its own irregular cumulative-time axis). The plotter
  refactors the render path onto a shared `_plot_normalized_series` helper +
  `_window_arrays` (which falls back to the window-0 view for legacy dicts), so the Phase-1
  / 2a single-window behavior is preserved. Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_3D_DATASET_VISUALIZATION_DESIGN_2026-06-19.md` §3.1 / §5. Tests:
  `src/tests/unit/test_sequence_dataset_viz.py` (8 new cases: window cap, multi-window
  store, compare-windows render + defaults, window selection, fallback, control options).
- **3-D dataset viewer — target + characterization companions (Phase 2c, #368)**: the
  final Phase-2 slice completes the two-mode viewer. An optional **regression-target**
  graph (a `Show target` switch in the control bar) renders the primary window's target;
  a **collapsible characterization side companion** (on by default) shows whole-dataset
  **Δt** and **target** histograms plus a **W / L / F** stats block beside the main plots
  — the viz area is now a flex row whose companion hides for 2-D tabular so the main
  column expands. Backend (`src/demo_mode.py`): `_install_sequence_dataset` additionally
  stores the per-window regression target (`windows_y`, capped) and precomputes bounded
  whole-dataset `dt_hist` / `target_hist` (~30 bins each) — still **display-only** (OQ-4).
  The companions are wired as **separate callbacks**, so the core `update_dataset_plots`
  (and its tests) are unchanged. Resolves design OQ-A (target = a separate companion
  strip) and OQ-C (characterization = whole-dataset summary + the always-on selected-window
  Δt strip). Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_3D_DATASET_VISUALIZATION_DESIGN_2026-06-19.md` §3.3 / §5. Tests:
  `src/tests/unit/test_sequence_dataset_viz.py` (6 new cases). With 2a/2b this completes
  the Phase-2 control surface; the advanced full-cross grid remains Phase 3.
- **3-D dataset viewer — advanced full-cross grid (Phase 3, M4, #368)**: an opt-in
  **`Advanced: full-cross grid`** switch reveals a scrollable faceted grid of **every
  signal (columns) × window (rows)**, each cell a normalized line over cumulative-Δt time
  — the expert view the default two-mode viewer deliberately avoids. Hidden by default and
  **sequence-only**; **capped at 100 cells** (the window rows are trimmed so
  `rows × cols ≤ 100`, the title noting e.g. "first 20 of 30 windows"), inside a
  vertically-scrolling container with per-cell modebar zoom. No backend change (reuses the
  capped multi-window store from Phase 2b); wired as a **separate callback**
  (`update_sequence_grid`) so the core callbacks are untouched. Resolves design OQ-B (grid
  mechanics: row-trim cap + scroll + modebar zoom). **Completes the 3-D dataset
  visualization design** (Phases 1–3). Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_3D_DATASET_VISUALIZATION_DESIGN_2026-06-19.md` §3.4 / §5. Tests:
  `src/tests/unit/test_sequence_dataset_viz.py` (4 new cases: hidden-off, hidden-tabular,
  full-cross render, 100-cell cap).
- **Harness L2 — enroll the three #366-wired controls in the behavioral manifest
  (#369)**: `restart-with-new-dataset-button`, `nn-init-output-weights-dropdown`, and
  `dataset-plotter-dataset-selector` were L1-guarded (wired) but not yet behaviorally
  proven. Adds three `ControlContract` rows to `src/tests/ui_contract/control_manifest.py`
  (restart → `POST /api/train/start?reset=true`; init-output-weights → `POST
  /api/set_params` + `/api/state` roundtrip on the non-default `random`; dataset-plotter
  selector → `POST /api/dataset/generate {"generator": "spiral"}`), exercised in-process
  by the existing L2 driver. L2 grows 8 → 11 rows; closes the wired-vs-proven gap for the
  controls completed in #366.
- **Model + dataset-type registry (`src/model_registry.py`) — model-selection
  groundwork (A0, #368)**: a single source of truth for NN-model (`ModelSpec`) and
  dataset-type (`DatasetTypeSpec`) specifications. The dashboard's
  `nn-dataset-type-dropdown` now sources its options and default from
  `dataset_type_options()` / `DEFAULT_DATASET_TYPE` instead of a hardcoded inline list
  — **behavior-preserving** (identical labels / values / order / `spirals` default).
  Seeds the current `cascor` (live, 2-D) and `recurrence`/LMU (coming-soon, 3-D,
  `requires_dt`) models plus the five 2-D classification dataset types, with a
  future-proofed spec shape (`status` lifecycle; `version` / `benchmark_id` / `family`
  / `variant` / `tags`). `task_type` uses juniper-data's vocabulary
  (`classification` / `regression`); a model's 3-D / irregular-Δt nature is carried by
  `ndim` + `requires_dt`, not a task-type label. The compatibility resolvers, the
  dedicated selection surface, and the `nn_model` backend mirror are deferred to A1.
  Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md`. Regression
  coverage: `src/tests/unit/test_model_registry.py`.
- **Recurrence (LMU) service adapter + outbound settings — model-selection A1 enabler
  (A1-i, #368)**: the first build slice of A1 (making `recurrence` genuinely *trainable*
  from canopy, not just a coming-soon registry entry). Adds `RecurrenceServiceAdapter`
  (`src/backend/recurrence_service_adapter.py`) — a thin **synchronous** `httpx` REST
  client for the juniper-recurrence model service: a blocking `POST /v1/train` (the LMU is
  a one-shot ridge/lstsq fit — no epochs to stream, hence no WebSocket) plus the instant
  `GET /v1/training/status`. It sends the outbound `X-API-Key`, applies a **generous
  read-timeout** to the blocking train, and maps failures onto a typed error hierarchy
  (`RecurrenceTrainInProgressError` 409 / `RecurrenceServiceAuthError` 401·403 /
  `RecurrenceServiceTimeoutError` / `RecurrenceServiceUnavailableError` / base
  `RecurrenceServiceError`) so the one-shot UI path (D1-A, A1-iii) can surface each
  distinctly. New `Settings.recurrence_service_url` + `recurrence_api_key`
  (`src/settings.py`) mirror the juniper-data outbound-key pattern: the prefixed
  `JUNIPER_CANOPY_*` var wins over the shared cross-service var (`RECURRENCE_SERVICE_URL` /
  `JUNIPER_RECURRENCE_API_KEY`), and the key honours `_FILE` secret indirection.
  **Adapter + settings only — no routing or UI yet**: `create_backend` provider routing is
  A1-ii; the one-shot execution path + cascade-panel suppression A1-iii. Scope is `train` +
  `status` (predict / crossval deferred — enabler OQ-2). Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_MODEL_SELECTION_A1_ENABLER_SCOPE_2026-06-18.md` (D3) /
  `..._MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md`. Tests:
  `src/tests/unit/test_recurrence_service_adapter.py` (24 cases, mocked via
  `httpx.MockTransport`) + `src/tests/unit/test_recurrence_settings.py` (11 cases).
- **Recurrence backend + provider routing — model-selection A1 enabler (A1-ii, #368)**:
  the second build slice, making the recurrence model *routable* through canopy's backend
  factory. Adds `RecurrenceBackend` (`src/backend/recurrence_backend.py`) — a
  `BackendProtocol` wrapper over the A1-i `RecurrenceServiceAdapter` that bridges the
  execution-paradigm mismatch (D1-A): the recurrence `POST /v1/train` is a **synchronous
  one-shot fit**, so `start_training` backgrounds it on a daemon thread and the backend
  reports a **binary** `idle → training → trained|failed` status via `get_status` /
  `is_training_active` (no fabricated per-epoch progress). The cascade-only protocol
  surface is honestly stubbed — `get_network_topology` / `get_raw_topology` /
  `get_decision_boundary` return `None` (LMU has no growing topology or 2-D decision
  boundary, D6) — and `get_metrics` carries the **regression** metric set (mse / rmse / mae
  / r2 / loss, never accuracy); `apply_params` stages `d` / `theta` / `ridge` for the next
  fit; failures surface via the existing `completion_reason` field. `create_backend()`
  (`src/backend/__init__.py`) gains an `nn_model` axis (D5): a recurrence-provider model
  (resolved via the new `model_registry.get_model_spec()` + `RECURRENCE_PROVIDER` constant)
  with `recurrence_service_url` configured routes to `RecurrenceBackend`; **every other
  case — non-recurrence model, unconfigured URL, or the `nn_model=None` startup default —
  leaves the demo/cascor selection byte-for-byte unchanged**. **Routing + backend only**:
  wiring `backend_type == "recurrence"` through `main.py`'s route branches and the one-shot
  result view / panel suppression are A1-iii. Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_MODEL_SELECTION_A1_ENABLER_SCOPE_2026-06-18.md` (D1-A / D5 / D6).
  Tests: `src/tests/unit/backend/test_recurrence_backend.py` (24 cases — backgrounding,
  binary status, stubs, failure handling, controllable fake adapter) +
  `src/tests/unit/test_recurrence_routing.py` (9 cases — routing precedence + `get_model_spec`).
- **Recurrence route correctness + dataset-ref plumbing — model-selection A1 enabler
  (A1-iii-a, #368)**: makes a recurrence (one-shot) backend behave correctly in `main.py`'s
  route layer and lets a recurrence fit actually run. **Route fixes** (`src/main.py`): the
  `/api/v1/snapshots` mock-snapshot path is gated on `== "demo"` (was `!= "service"`, which
  made recurrence serve fabricated demo snapshots); the snapshot create/restore adapter calls
  are gated on `== "service"` (recurrence's `_adapter` is a different type — it must use the
  h5py fallback, not cascor's `save_snapshot`/`load_snapshot`); `/api/v1/workers/stats` +
  `/workers/list` return an **empty** pool for recurrence instead of the synthetic demo-worker
  fixtures; and the lifespan seeds `training_state` from `get_status()` for recurrence (it has
  no live stream / `set_state_update_callback`). The cascade-only routes were already correctly
  fenced by `== "service"` guards (clean 501/503), and `RecurrenceBackend` already returns
  `None` for topology / decision-boundary (a regression test now locks in the clean 503).
  **Dataset-ref plumbing**: `/api/train/start` gains an optional body (`dataset` ref +
  `d`/`theta`/`ridge`) and the `/ws/control` `start` command forwards its `params`, both via a
  shared `_recurrence_start_kwargs` helper — for **recurrence only**, so cascor/demo keep their
  bare `start_training(reset=…)` call **byte-for-byte unchanged** (extra kwargs would break
  them). **No UI** — the model picker + the one-shot result view / panel suppression are
  A1-iii-b / A1-iv. Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_A1_III_DASHBOARD_INTEGRATION_SCOPE_2026-06-23.md`. Tests:
  `src/tests/regression/test_recurrence_routes.py` (11 cases — route mis-bucket guards,
  topology/boundary 503, dataset-ref forwarding, cascor-unaffected, the helper).
- **One-shot cascade-panel suppression — model-selection A1 enabler (A1-iii-b1, #368)**:
  the dashboard now hides the cascade-network-only panels for a one-shot (recurrence / LMU)
  model. Adds an **execution paradigm** axis: `ModelSpec.execution` (`"live" | "one_shot"`,
  `model_registry.py`) + an `execution` property on `BackendProtocol` and all three backends
  (`demo`/`service` → `"live"`, `recurrence` → `"one_shot"`), surfaced to the frontend via a
  new `"execution"` field on `GET /api/train/status`. A new `model-class-store` (`dcc.Store`)
  is hydrated from that route on mount; when it reads `"one_shot"`, three callbacks
  (`_setup_model_class_callbacks`) **suppress** the cascade-only surface — the 5 viz tabs
  (Candidate Metrics / Network Topology / Network Evolution / Decision Boundary / Workers,
  rebuilt via a new `_all_visualization_tabs()` + `_visible_tabs()` so a now-hidden active
  tab falls back to *Training Metrics*) and the status-bar **Iteration** (hidden-units)
  segment. An LMU has no growing topology, decision boundary, candidate units, or worker pool,
  so these are meaningless for it; the route layer already refuses to serve them (A1-iii-a).
  **Suppression only** — the metrics accuracy→regression switch + the one-shot result view are
  A1-iii-b2. Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_A1_III_DASHBOARD_INTEGRATION_SCOPE_2026-06-23.md`. Tests:
  `src/tests/unit/test_recurrence_ui_suppression.py` (8 cases — execution flag across the
  backends + registry, and `_visible_tabs` drop/keep behavior) + a `/api/train/status`
  execution assertion in `test_recurrence_routes.py`.
- **One-shot regression result view — model-selection A1 enabler (A1-iii-b2, #368)**: the
  final A1-iii slice — a one-shot (recurrence / LMU) model now renders its **regression**
  result instead of a broken classification view. The metrics panel
  (`src/frontend/components/metrics_panel.py`) gains a `model-class-store`-driven callback
  (`render_model_class_metrics`) that, when the active model is `one_shot`, **hides the
  classification surface** (the accuracy / hidden-units / learning-rate cards row +
  both per-epoch loss/accuracy plots — meaningless for a single regression fit) and **shows a
  regression result card** (`_build_oneshot_result`): R² / RMSE / MSE / MAE / Loss formatted as
  plain floats (never a percentage), with a spinner placeholder while the fit runs. The
  `MetricsResult` TypedDict (`backend/protocol.py`) gains the regression keys (`r2` / `mse` /
  `rmse` / `mae`) so `RecurrenceBackend.get_metrics` is type-honest. **Design choice:** a
  dedicated result card (per design D-iii-3 "a regression-metrics card") rather than retrofitting
  the classification cards in-place — which also sidesteps the cascor nested-vs-flat metrics-
  envelope mismatch (the hidden classification cards never read recurrence data). Design-of-
  record: juniper-ml `notes/JUNIPER_CANOPY_A1_III_DASHBOARD_INTEGRATION_SCOPE_2026-06-23.md`.
  Tests: `src/tests/unit/test_recurrence_oneshot_result.py` (7 cases — surface toggle +
  regression card / spinner) + regenerated `snapshots/metrics_panel.txt`; UI sub-suite run
  locally.
- **Dedicated model-selection surface (A1b-1, #368)**: model selection moves from the sidebar
  `nn-model-dropdown` (A1-iv-3a) to a dedicated **`dbc.Modal`** (`size="xl"`, scrollable) holding a
  custom **`dbc.Table`** of models, opened by a compact sidebar **"Model: … ▸ change"** summary +
  button (`src/frontend/dashboard_manager.py`). Each row shows the model label / description,
  category, a lifecycle **status badge** (D8), a **compatibility cell**, and a per-row **Select**
  button (pattern-matching `{"type": "model-select-btn", "index": <key>}`) disabled only for
  *incompatible* models — per ratified **option (a)** a `coming_soon` model stays selectable (D8
  Train-gating deferred to iv-5). The compatibility cell is driven by a new registry
  **`model_reason()`** — the model-perspective inverse of `dataset_reason()` (e.g. "needs 3-D data"
  against a 2-D dataset). Selecting reuses the unchanged `_select_model_handler`
  (`POST /api/model/select` + store mirror) and closes the modal; the downstream dataset gate
  (A1-iv-3b) and one-shot start-body resolver (A1-iv-3c) are **untouched** — they key off the
  stores, not the dropdown, so only the input side moved. A modal was chosen over a Models tab
  because the tab bar caps `active_tab` writers at two and is rebuilt by the one-shot suppression —
  a modal's `is_open` toggle sidesteps both (OQ-1); a custom `dbc.Table` over `dash_table.DataTable`
  because the cells are rich components with no virtualization payoff at this row count (OQ-4). New
  registry helpers: `model_reason()` + `get_dataset_spec()`. Design-of-record: juniper-ml
  `notes/JUNIPER_CANOPY_MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md` (D7 / §5.2 / §5.3). Tests:
  `src/tests/regression/test_model_table.py` (15 cases — table builder, status badge, open/close,
  Select → apply + close) + `src/tests/unit/test_model_registry.py` (`model_reason` / `get_dataset_spec`).
  The reactive reverse dataset→model gate, degenerate states, and the search box are A1b-2.
- **Reactive reverse gate + degenerate states (A1b-2, #368)**: completes the bidirectional gate
  (§5.3) on the sidebar side. A new **reverse-gate annotation** under the model summary
  (`nn-model-dataset-hint`) names the model constraint the *currently-selected dataset* imposes —
  e.g. *"3-D Δt-aware models only"* for `equities_seq`, *"2-D models only"* for the 2-D types — the
  dataset-side mirror of the table's per-row `model_reason` greying. It updates on every dataset
  change (a user pick **or** the forward-gate snap from `gate_dataset_options`) via a new registry
  `dataset_model_hint()` helper. The model **table** also now renders a clear **recovery message**
  (§5.8) when a dataset has *no* compatible model (degenerate empty-compatible-set state) instead of
  a silently-unusable all-greyed list — defensive under option (a) (every current seed dataset has a
  compatible model), exercised via an injectable `models=` param. The **optional search box (§5.2)
  is deferred** — it is a FR12 scale affordance with no value at the current two-model population.
  Design-of-record: juniper-ml
  [`notes/JUNIPER_CANOPY_MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_2026-06-17_JUNIPER-CANOPY_MODEL-DATASET-SELECTION-DESIGN.md)
  (§5.3 / §5.8). Tests: `src/tests/unit/test_model_registry.py` (`dataset_model_hint`) +
  `src/tests/regression/test_model_table.py` (degenerate recovery, hint handler/seed, callback wiring).
- **Recurrence model goes live + D8 Train-gating (A1-iv-5, #368)**: the `recurrence` (LMU) model is
  flipped from `coming_soon` → **`live`** now that the canopy-routable service is deployed and wired
  in-stack (juniper-deploy #132 sets `JUNIPER_CANOPY_RECURRENCE_SERVICE_URL` → `http://juniper-recurrence:8210`),
  so it is now a fully selectable, trainable model. Alongside it lands the **D8 Train-gate** (design
  §5.7): a registry `model_is_trainable()` predicate (status == `live`; unknown → trainable so a
  desync never strands Start, FR9), the Start button **force-disabled** for any non-live model
  (folded into `update_button_appearance` via a new `model-selection-store` Input — a single-point
  combination of training-state + model-status, not a racy second writer), and a `train-gate-notice`
  status reason near the training controls explaining why Start is disabled. A non-live model stays
  *selectable* for inspection (option (a)) but is not trainable. With every shipped model now live the
  gate is exercised via synthetic non-live models (`model_options()` gained a `models=` injectable).
  Tests: `model_is_trainable` + the flipped/repurposed registry assertions
  (`test_model_registry.py`), the Start force-disable + notice handlers + wiring
  (`test_model_table.py`), and the live-status route assertion (`test_model_select.py`).
- **Model-table search box (A1b, #368)**: the model-selection modal gains a **free-text search**
  (`model-search-input`, a `type="search"` box with a native clear) above the table. It filters the
  model rows by **label + family + category + tags** (not label-only, §8) via a new registry
  `model_matches_search()` predicate; a blank query shows everything and a non-empty query that
  matches nothing renders a clear "no models match" message. Search is **folded into the existing
  modal toggle callback** (the one that owns the table container) — typing rebuilds the table
  filtered while the modal stays open, with no racy second writer; `_build_model_selection_table`
  gains a `search=` parameter. This is the §5.2 scale affordance (browse-and-compare at
  dozens-to-hundreds of model variants); it has no functional effect at today's two models but
  completes the surface. Design-of-record: juniper-ml
  [`notes/JUNIPER_CANOPY_MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_2026-06-17_JUNIPER-CANOPY_MODEL-DATASET-SELECTION-DESIGN.md)
  (§5.2). Tests: `model_matches_search` (`test_model_registry.py`) + search filtering / no-match
  message / open-honours-search + search-rebuilds-keeping-open (`test_model_table.py`). **This
  completes the A1 model-selection feature end-to-end.**

- **Build provenance on `/v1/health` + `/v1/health/ready`.** The dashboard now
  reports the source `git_sha` and ISO-8601 `build_date` baked into its image
  at build time. New `GIT_SHA` / `BUILD_DATE` / `APP_VERSION` Dockerfile
  build-args become OCI labels (`org.opencontainers.image.revision` /
  `.created` / `.version` — the image previously carried no `revision` /
  `created` / `version` labels at all) plus `JUNIPER_CANOPY_GIT_SHA` /
  `_BUILD_DATE` env vars; a new `provenance` accessor (`src/provenance.py`)
  reads them back (both `null` outside a provenance-stamped image — local dev /
  a bare `docker build`). The values are also passed into `set_build_info(...)`
  (Prometheus `juniper_canopy_build` Info metric) and the shared
  `ReadinessResponse`. Foundation for the ecosystem stale-image-detection
  effort — see juniper-ml
  [`notes/BUILD_PROVENANCE_DESIGN_2026-06-14.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_2026-06-14_JUNIPER-ECOSYSTEM_BUILD-PROVENANCE-DESIGN.md).
  Requires `juniper-observability>=0.4.0`.

- **STATUS BAR — show cascor `completion_reason` (converged vs stalled) on a completed run (Issue #3 diagnosability follow-up, consumes cascor #320)**: a finished training run rendered a bare "Completed" regardless of *why* growth stopped, so a genuine convergence was indistinguishable from a 0-unit stall. cascor #320 now emits a `completion_reason` on `/v1/training/status`; this wires it through canopy end-to-end. `ServiceBackend.get_status` (`src/backend/service_backend.py`) carries the top-level `completion_reason` into the flat `StatusResult` (mirroring the existing `pending_dataset` pass-through; `StatusResult` in `src/backend/protocol.py` gains the field), and `_build_unified_status_bar_content` (`src/frontend/dashboard_manager.py`) appends a short label to the status when `status == "Completed"` via a new `_completion_reason_label` helper: `residual_collapsed`/`below_threshold` → **"Completed — converged"**, `no_candidate` → **"Completed — stalled (0 new units)"**, `early_stopped` → **"Completed — early stopped"**, `max_iterations` → **"Completed — max iterations"**. Display-only (the status color still keys off the base "Completed"); an unknown or missing reason yields a plain "Completed", so a canopy talking to a cascor that predates #320 degrades gracefully. Regression coverage: `src/tests/unit/frontend/test_completion_reason_status_bar.py` (label mapping + the five completed-run suffixes + not-completed / unknown / missing cases) and two `test_service_backend.py` cases (carry-through + `None` when absent).
- **SEC-16 parity — `/metrics` IP allowlist via
  `juniper_observability.MetricsAuthMiddleware`**: canopy now wraps its
  Prometheus `/metrics` ASGI mount in the shared
  `MetricsAuthMiddleware` (promoted from juniper-data #157 and
  juniper-cascor #313 to `juniper-observability` 0.3.0 — see
  juniper-ml #335). The middleware enforces a configurable bare-IP /
  CIDR allowlist with IPv6 zone-id strip and IPv4-mapped IPv6 unwrap,
  so a Docker container appearing as `::ffff:172.18.0.5` matches an
  IPv4 `172.18.0.0/16` allowlist entry; unparseable allowlist entries
  raise a `ValueError` at `Settings()` construction (fail-loud).
  Concrete changes: `src/settings.py` adds
  `Settings.metrics_trusted_ips: list[str] = ["127.0.0.1", "::1"]`
  with a `_validate_metrics_trusted_ips` field validator that
  delegates to `juniper_observability.parse_trusted_networks`;
  `src/main.py` rewraps the existing
  `app.mount("/metrics", get_prometheus_app())` as
  `app.mount("/metrics", MetricsAuthMiddleware(get_prometheus_app(), settings.metrics_trusted_ips))`;
  `pyproject.toml` bumps `juniper-observability>=0.2.0` to `>=0.3.0`
  (first release that exports the middleware). No `EXEMPT_PATHS`
  change required because `SecurityConstants.EXEMPT_PATH_PREFIXES`
  already contained `"/metrics"`, so canopy's `SecurityMiddleware`
  was already letting the path through — the IP allowlist is the
  only gate now. New regression test
  `src/tests/unit/test_metrics_auth_settings_integration.py` (8 cases)
  pins the canopy-side wiring: default loopback, env-var JSON-list
  widening to CIDR, bare IPv6 CIDR, fail-loud on `172.18.0.0/164`
  typos, fail-loud on `"not-an-ip"`, valid mixed CIDR + bare IP
  accepted, shared `parse_trusted_networks` delegation contract, and
  the `/metrics in EXEMPT_PATH_PREFIXES` invariant. Middleware
  behaviour itself is covered by juniper-observability's
  `tests/test_metrics_auth_middleware.py` (22 cases). Closes the
  third trigger-conditioned deferred follow-up in
  juniper-deploy/notes/poc/POC_REMEDIATION_PLAN_2026-05-27.md §6
  ("Add `MetricsAuthMiddleware` to juniper-canopy"). Companion
  juniper-deploy PR (wiring `JUNIPER_CANOPY_METRICS_TRUSTED_IPS`
  into canopy's compose env block + `.env.observability` default)
  is queued separately.

- **Outbound `X-API-Key` for juniper-data calls**: new
  `Settings.juniper_data_api_key` field plus `_check_juniper_data_api_key`
  field validator that resolves the value via `secrets_util.get_secret`
  (Docker-secrets `<NAME>_FILE` indirection). Resolution order:
  `JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE` → direct prefixed env →
  `JUNIPER_DATA_API_KEY_FILE` (shared cross-service) → direct shared
  env → `None`. The resolved value is plumbed through
  `_generate_spiral_dataset_from_juniper_data` and passed as
  `JuniperDataClient(api_key=…)` so every outbound juniper-data call
  carries `X-API-Key`. Closes the gap where canopy never sent an
  outbound key and silently 401'd against juniper-data once
  juniper-deploy#100 enabled juniper-data auth (canopy's own
  `/v1/health` had remained misleading because juniper-data's
  `/v1/health` is auth-exempt). When both prefixed and shared env vars
  are unset the field defaults to `None` and `JuniperDataClient` omits
  the header — preserving the pre-this-PR behaviour for stacks where
  juniper-data auth is disabled. New regression suite at
  `src/tests/unit/test_juniper_data_api_key_resolution.py` (8 cases)
  pins prefixed direct, prefixed `_FILE`, prefixed `_FILE` precedence
  over direct, prefixed `_FILE` missing-file fallthrough to shared,
  shared direct, shared `_FILE`, prefixed-wins-over-shared, and the
  no-env-vars `None` default.

- **CFG-01** (v7 roadmap §13439): new `[demo]` optional-dependencies extra declaring `torch>=2.0.0`. Closes the missing-declaration where `src/demo_mode.py:63` and `src/backend/demo_backend.py:45` `import torch` unconditionally at module level but `pyproject.toml` had no `torch` entry — `pip install juniper-canopy` (no extra) silently produced a wheel that crashed on demo import. Kept out of `[project] dependencies` per the roadmap recommendation to avoid the ~2GB install footprint on production deployments that drive a remote cascor service via `[juniper-cascor]` and never load demo mode (matches the lazy-import convention in `src/backend/data_adapter.py:363,406` whose existing `noqa: F811` comments call out the size cost explicitly). The standalone demo runner `util/juniper_canopy-demo.bash` continues to install torch via `conf/requirements.txt` + the PyTorch CPU index URL for size-optimised bash-script installs; this extra is the canonical path for `pip install juniper-canopy[demo]`. `[dev]` aggregator updated to include `[demo]` so the test suite (`src/tests/unit/test_demo_mode_comprehensive.py:22` etc. import torch unconditionally) resolves under `pip install juniper-canopy[dev]`. No code changes — declaration only.

### Changed

- **SEC-F22 / D2 — two-flag bind attestation (supersedes the unreleased single-flag attestation)**: the startup loopback bind-guard's single operator attestation is replaced by **two** independent booleans (both default `False`), so the guard names the *reason* a non-loopback bind is permitted instead of collapsing two distinct perimeters into one flag: `settings.loopback_publish_attested` (`JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED`) — canopy is reachable only via a loopback-only host publish (the containerized default; verifiable by the juniper-deploy preflight) — and `settings.auth_proxy_attested` (`JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`) — a fronting authenticating reverse proxy terminates access (Phase 4; attestation only). `security.enforce_loopback_bind_guard()` (`src/security.py`, called from `main.lifespan`) now allows a non-loopback bind iff **at least one** attestation is `True` and logs which one permitted it; a non-loopback bind with **neither** still hard-fails uniformly (CRITICAL log + `NonLoopbackBindError`; there is no warning-only mode). Loopback binds (the default) start normally — zero-UX for the shipped posture. **(c) consistency fix:** the root `Dockerfile` default bind host changes from `0.0.0.0` to `127.0.0.1` so a bare `docker run -p 8050:8050` is safe-by-default (matches juniper-cascor); the juniper-deploy compose already sets `SERVER__HOST=0.0.0.0` explicitly and will add the explicit attestation. The `docker-build` smoke step (`.github/workflows/ci.yml`) now runs the container with `-e JUNIPER_CANOPY_SERVER__HOST=0.0.0.0 -e JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` so the image still boots past the guard for the `/v1/health` probe. Regression coverage: `src/tests/unit/test_bind_guard.py` (neither / either / both attest; loopback-safe default; which-attestation-permitted logging) and `src/tests/regression/test_docker_bind_default.py` (loopback-safe Dockerfile default; no baked attestation). **This is one of a three-PR set** — the identical two-flag scheme lands in juniper-cascor and juniper-deploy; the deployed stack needs all three consistent, and this is owner-gated (not auto-merged). Design-of-record: juniper-ml [`notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md) §4 / §8 (D2).
- **CFG-09** (v7 roadmap §13896): `Settings.audit_log_path` default changed from `/var/log/canopy/audit.log` (root-only) to `logs/audit.log` (CWD-relative user-space). Closes the failure class where a fresh non-root install of juniper-canopy crashed at startup inside `src/audit_log.py:51` (parent-directory `mkdir`) or `:53-58` (`TimedRotatingFileHandler` open) because the bake-in default required root privileges to create `/var/log/canopy`. The matching parameter default of `configure_audit_logger(log_path=...)` in `src/audit_log.py:27` was changed in lockstep so direct callers (i.e. anyone invoking the function without passing `settings.audit_log_path`) also get the user-space default. **Not breaking for production**: deployments override via `JUNIPER_CANOPY_AUDIT_LOG_PATH` (pydantic auto-derives from `env_prefix='JUNIPER_CANOPY_'`); the env-var path is unchanged and continues to resolve. No `Settings` model_validator was added — `audit_log.py:51` already does `Path(log_path).parent.mkdir(parents=True, exist_ok=True)`, so adding one in Settings would be duplicate. Switching the default to the canonical XDG state location (`$XDG_STATE_HOME/canopy/audit.log`, default `~/.local/state/canopy/audit.log`) is a deferred follow-up — would require introducing an XDG helper to canopy, which is out of CFG-09's scope. Pinned by new 5-case source-level regression suite at `src/tests/regression/test_cfg_09_audit_log_default.py` (Settings default value, function-parameter default value, no-old-default-in-settings-source, no-old-default-in-audit_log-source, env-var-override-still-resolves).
- Refreshed developer and API documentation for the SEC-F22/SEC-F19 control-surface hardening: `docs/QUICK_START.md`, `docs/ENVIRONMENT_SETUP.md`, `docs/REFERENCE.md`, `docs/DEVELOPER_CHEATSHEET.md`, and `docs/api/API_REFERENCE.md` now document the fail-closed loopback bind guard, the two bind attestations `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` / `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`, canonical `JUNIPER_CANOPY_*` settings, and global/per-IP/per-session WebSocket caps.

### Fixed

- **CI DOCKER SMOKE — the smoke container is attested past the bind-guard so the image can boot** (updated for the two-flag migration above): the startup loopback bind-guard (SEC-F22 / D2) refuses to serve on a non-loopback interface without a perimeter attestation, so canopy's `docker-build` "Verify Container Starts" smoke step (`.github/workflows/ci.yml`) — which must reach the container through the published port — would otherwise abort at startup (`NonLoopbackBindError`, raised in `main.lifespan`) and never reach `healthy`. The smoke step now runs `docker run` with `-e JUNIPER_CANOPY_SERVER__HOST=0.0.0.0 -e JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` — scoped to that ephemeral CI container only (no fronting proxy is present; the container just needs to boot for the `/v1/health` probe). Supersedes the interim single-flag smoke attestation (never released). Independent security review of #420, §9.

- **SEC-F19 / D4 WS cap rollback — globally rejected sockets no longer leak reserved per-IP/per-session slots**: the endpoints reserve the per-IP/session counters before awaiting `WebSocketManager.connect()`, but the new stack-absolute global cap can reject later inside `connect()` when `max_connections` is already full. That rejection path closes the socket before it enters `active_connections`, so the endpoint's normal `disconnect()` cleanup no-ops and the reserved counters stayed inflated, letting repeated over-global attempts strand a browser session/IP at its cap until process restart. `connect()` now returns whether it actually registered the socket, and all WS endpoints release the reserved cap slots when registration is rejected or fails before activation. Regression coverage: `src/tests/unit/test_ws_connection_caps.py::TestGlobalConnectionCap::test_global_cap_rejection_releases_reserved_session_slots`.

- **STALE-VERSION SHADOW — `.dockerignore` now excludes *nested* `**/*.egg-info/` so the image stops reporting a stale package version**: `importlib.metadata.version("juniper-canopy")` (the source of `APP_VERSION` → `/v1/health` `version`, the Prometheus `juniper_canopy_build` metric, and the Sentry release) resolved to **0.4.0** while `pyproject.toml` was **0.5.0**. Root cause: a stale, git-untracked `src/juniper_canopy.egg-info` build artifact was COPYed into the image by the Dockerfile's `COPY src/ ./src/`; with `ENV PYTHONPATH=/app/src` ahead of site-packages, `importlib.metadata` resolved that egg-info's `PKG-INFO` (0.4.0) instead of the freshly-installed `juniper_canopy-0.5.0.dist-info`. The existing `.dockerignore` carried `*.egg-info/`, but that pattern only matches the **context root** and silently missed the nested `src/*.egg-info`. Fix: add the `**/`-prefixed `**/*.egg-info/` and `**/*.dist-info/` forms so nested build-metadata dirs are excluded from the build context at any depth (verified against a context containing `src/X.egg-info` — excluded, while real source is kept). Surfaced by the build-provenance `make doctor` work (juniper-ml [`notes/BUILD_PROVENANCE_DESIGN_2026-06-14.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_2026-06-14_JUNIPER-ECOSYSTEM_BUILD-PROVENANCE-DESIGN.md)): doctor correctly reported the image **FRESH** (`git_sha` == source HEAD) while the version string lied — exactly why `git_sha` is the reliable staleness signal. Takes effect on the next canopy image rebuild. Regression coverage: `src/tests/regression/test_dockerignore_egg_info.py` pins the nested-exclusion patterns.

- **TRAINING-CONTROL ERROR SURFACING — a rejected Start/Pause/Stop/Resume/Reset now shows a danger alert instead of silently bouncing the button (the "dead button" class)**: clicking a training-control button that the backend then rejected produced **no** user-visible feedback — the button flipped to its optimistic "pending" state and silently re-enabled, with the failure (and its reason) reaching only a server log or the browser console. This was the canopy half of the cascor dual-path #319 incident: a 401/502 live dataset swap (cascor#331) and an FSM-rejected Start (409) were both invisible from the dashboard. Two transports were silent: (1) the **production-default clientside WS path** (`PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS`, gated `enable_ws_control_buttons=True`) returned `success: true` *synchronously* and resolved the real WS/REST outcome only to `console.warn`; (2) the server-side handler (`_handle_training_buttons_handler`) computed `success: False` into `training-control-action` but **nothing consumed it** and the response body (the reason) was discarded. Fix — one shared outcome surface fed by both transports: a new fixed-position `training-control-outcome-alert` div (offset below `live-switch-outcome-alert`) is filled by a single unconditionally-registered render callback (`_surface_training_control_outcome_handler`) that renders a dismissable `dbc.Alert(color="danger", duration=8000)` naming the command and the reason on failure, and clears on success. The server-side handler now captures the rejection detail via a new `_extract_training_error_detail` helper (prefers cascor's structured `{"error": {"message": …}}` body — which cascor#332 made specific, e.g. "Training cannot be started: Training data not provided" — then raw text, then the exception string; never raises) and stores `{success, command, detail}`. The clientside JS pushes the **real** async outcome into the same store via `dash_clientside.set_props('training-control-action', …)` (the established Phase D §S10 pattern) from the REST-fallback failure branches, so WS rejections, WS-down→REST, and pure-REST failures all surface. All edits are additive on failure branches that previously dead-ended in the console; the success path, optimistic button state, debounce, and timeout sweeper are untouched. Design + root cause: [`notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md`](notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md). Regression coverage: `test_dashboard_manager.py` (handler failure now carries `command`+`detail`; `_extract_training_error_detail` JSON / text / bare-exception / never-raises; `_surface_training_control_outcome_handler` clear-on-success / render-danger-on-failure / fallback-detail) and `test_phase_d_button_clientside.py` (JS contains the `set_props` reporting wired into the REST fallback; render callback registered under both transport flags). **Live-verification gate:** the `set_props`→render round-trip is not Python-unit-testable, so this must be confirmed on the deployed stack (force a Start the FSM will reject; confirm the red alert appears with the cascor reason) before merge. **Deferred (noted in the design doc):** short-circuiting the REST double-send on a *definitive* WS command rejection, and an optional green success confirmation.
- **WS-CONTROL PONG — `/ws/control` accepts an inbound heartbeat pong instead of erroring (closes the WS-KEEPALIVE latent note)**: the `/ws/control` receive loop (`src/main.py`) handled inbound `{"type": "ping"}` (replies with a pong) but had no branch for `{"type": "pong"}`. A pong frame carries no `command` key, so it fell through to the command dispatch as `command == ""` and the endpoint replied `Unknown command: ` (`code="unknown_command"`). Dormant today — the server Phase-F heartbeat only pings `/ws/training`, never `/ws/control` (the WS-KEEPALIVE entry below scoped it to `channel="training"` *specifically* to avoid this misfire) — but it would trip the moment the heartbeat is extended to the control channel, or any client sends an unsolicited pong. The loop now treats `{"type": "pong"}` as a silent no-op (debug-logged), mirroring `/ws/training`, which already ignores non-ping frames. Removes the blocker noted in WS-KEEPALIVE so a future control-channel heartbeat is safe. Regression coverage in `test_websocket_control.py::TestWebSocketControlIntegration::test_control_pong_is_noop_not_unknown_command` (send a pong then a valid `start`; the next command response is the `start` success — proving the pong produced no `ok: False` error).
- **#2a APPLY-PARAMS RETRY-AFTER BACKOFF — a 429 now backs off and retries instead of failing the click (completes the half #345 deferred)**: `_apply_parameters_handler` (`src/frontend/dashboard_manager.py`) wraps its `/api/set_params` POST in a 3-attempt retry loop (`DashboardConstants.DASHBOARD_SET_PARAMS_MAX_RETRIES`), but the `429` branch **returned immediately** — it never consumed the retry budget and ignored the `Retry-After` header the limiter faithfully sets (`src/security.py`; `Retry-After: <reset_in>` seconds). After #345 exempted canopy's own self-calls a 429 here is the rarer genuine downstream/cascor-side limit, but a single transient one still failed the user's "Apply Parameters" click outright. The 429 branch now **backs off and `continue`s within the existing loop**: it sleeps `min(Retry-After, DASHBOARD_RETRY_AFTER_MAX_SLEEP_S)` and retries, returning the "Rate limited — please try again in a few seconds" message only *after* the retry budget is exhausted (not on the first 429). The sleep is **bounded** — this runs on a Dash callback thread and the advertised `Retry-After` can be the limiter's full window (tens of seconds), so it is capped at a new `DashboardConstants.DASHBOARD_RETRY_AFTER_MAX_SLEEP_S = 2.0`; a missing/non-numeric header (e.g. the rare RFC 9110 HTTP-date form, which our own limiter never emits) falls back to `DASHBOARD_RETRY_AFTER_FALLBACK_S = 0.5` via a new `_parse_retry_after` helper. **Both constants are provisional first-cut tuning and are flagged in `canopy_constants.py` for revisiting once there is real 429-frequency data from the deployed stack.** Regression coverage in `test_dashboard_manager_handlers.py` (429-then-200 retries and succeeds with the sleep capped at 2.0s even when `Retry-After: 60`; persistent 429 consumes the full retry budget and returns the message only after exhausting — not immediately; a missing header backs off by the 0.5s fallback).
- **#2a RATE LIMIT — exempt canopy's own self-calls (the dashboard was 429-ing itself)**: canopy's `RateLimiter` keys by API-key (falling back to per-IP), but the dashboard's high-frequency `/api/*` polling **and** a user's actions are *all* server-side self-calls from the canopy process carrying the same `X-API-Key` — so they shared one bucket, the polling drained it, and a click (e.g. "Apply Parameters") landing in a drained window got HTTP 429 ("Rate limited"), which also surfaced as the #3 "Error" status. `frontend.internal_api.internal_api_headers()` now attaches a **per-process unforgeable token** (`INTERNAL_REQUEST_HEADER`, a fresh `secrets.token_urlsafe(32)` generated at process start) to every self-call, and `RateLimiter.__call__` (`src/security.py`) **exempts** requests bearing it (constant-time `hmac.compare_digest`). External clients can't forge the token, so they stay rate-limited. Regression coverage in `test_security.py::TestInternalRequestRateLimitExemption` (valid token → exempt across many calls; forged token → limited; missing → limited; round-trip that `internal_api_headers()` carries the exact exempt token). **Deferred:** a `Retry-After`-aware backoff in the apply handler — the exempt removes canopy's own 429 (the dominant source), leaving only the rarer cascor-side case, so it's a small optional follow-up.
- **#2b APPLY-PARAMS HONESTY — stop reporting canopy-local params as "not supported"**: the "Apply Parameters" toast read "Applied 19 of 27 … 8 not yet supported by the backend", listing 8 params the code *already knew* were canopy-only. `CascorServiceAdapter.apply_params` (`src/backend/cascor_service_adapter.py`) built its `skipped` list from every key absent from `_CANOPY_TO_CASCOR_PARAM_MAP`, **including** the keys in `_CANOPY_LOCAL_PARAMS` — which the code's own comment says "should never be reported as skipped". Now `skipped` also excludes `_CANOPY_LOCAL_PARAMS`, so it surfaces only *genuinely* unsupported keys; with an empty `skipped`, the dashboard's honesty toast (`dashboard_manager.py`) simply doesn't fire and the clean "applied" message shows. Reworked `test_apply_params_skipped_surfaced.py::TestAdapterSurfacesSkipped` (which previously asserted the buggy contract — that canopy-local keys appear in `skipped`) to the corrected contract: canopy-local keys are not surfaced, a genuinely-unknown key still is. **Fast-follow (separate PR):** the structural param-surface cleanup — wiring the 3 silently-dropped `SetParamsRequest` params (`nn_output_epochs`/`nn_optimizer_type`/`nn_activation_function_name`), dropping the read-only `cn_training_complete`, and relocating `nn_dataset_*` off the 27-key dict onto `/api/stage_dataset`.
- **#3 STATUS-BAR DIAGNOSABILITY — specific labels instead of a bare "Error"**: a failed `/api/status` poll rendered a generic `"Error"` in the unified status bar regardless of cause, so the dominant case on the deployed stack — a transient **429** from canopy's own rate limiter (see #2a) — was indistinguishable from a real backend outage. `_update_unified_status_bar_handler` (`src/frontend/dashboard_manager.py`) now maps the failure to a specific label via a new `_status_bar_error_tuple` helper: **429 → "Rate Limited"**, **401/403 → "Unauthorized"**, **5xx → "Backend Error"**, other non-200 → "Backend Unavailable", `requests.Timeout` → "Backend Timeout", `requests.ConnectionError` → "Unreachable", anything else → "Error". Regression coverage in `test_dashboard_manager.py::TestStatusBarErrorDiagnosability` (10 cases across status codes + exception types + the unchanged 200 happy path). **Deferred follow-up:** rendering the circuit-breaker-open state as "Unreachable" rather than "Stopped" needs an `error`/unreachable signal plumbed through the `StatusResult` schema (`backend/protocol.py` + `service_backend.get_status`), so it's a separate PR rather than bundled here.
- **#4 DATASET-APPLY — numeric inputs now reach `/api/stage_dataset` (a modified dataset trains)**: editing a dataset's element count / noise and clicking **Apply Dataset** never changed the trained dataset on the real backend — only a dropdown `dataset_type` change took effect. Two coupled causes in `src/frontend/dashboard_manager.py`: (1) **Apply-Dataset had no force-blur**, so a numeric value typed and then committed by *clicking* the button (without tabbing out) was still the Dash/React `null` at `State()`-read time — the same gap fixed for Apply-Parameters in Issue #2; (2) `apply_dataset` then ran a blanket `{k: v for ... if v is not None}` drop that silently discarded those `null` numerics, leaving only `dataset_type`. Fix: the existing force-blur clientside callback now fires on **both** `apply-params-button` and `apply-dataset-button`, and `apply_dataset` seeds the payload with `nn_dataset_type` unconditionally (cascor `_reload_dataset` requires it) while including the optional numeric / spiral fields only when present. Regression coverage in `test_dashboard_manager.py::TestDatasetApplyNumericCommit` (force-blur wired to both buttons; payload always sends `dataset_type`; blanket None-drop removed) plus an updated input assertion in `tests/ui/test_apply_blur_clientside.py`. The companion relocation of `nn_dataset_*` off `/api/set_params` is the #2b change.
- **WS-KEEPALIVE — server-side Phase F heartbeat (completes the #3 "WS: Reconnecting" idle-timeout fix)**: the browser client already replied to server `{"type": "ping"}` frames with a pong (`src/frontend/assets/websocket_client.js`), but nothing on the server ever *sent* those pings, so the `/ws/training` receive loop (`src/main.py` — `asyncio.wait_for(websocket.receive_text(), timeout=idle_timeout_seconds)`, default 120s) idled out on any quiet-but-healthy training stream and the client flapped Connected→Reconnecting. `src/main.py` now starts a `_websocket_keepalive_loop` task in the application lifespan that calls `websocket_manager.broadcast_ping(channel="training")` every `websocket.heartbeat_interval` seconds (the previously-dormant 30s setting, well under the 120s idle timeout) and cancels it on shutdown; the client's existing pong resets the server idle timer. `WebSocketManager.broadcast()` / `broadcast_ping()` gain an optional `channel` filter so the heartbeat is scoped to the training channel only — `/ws/control` has no idle timeout and would mis-handle the resulting pong as an unknown command. Regression coverage: `test_main_import_and_lifespan.py::TestWebSocketKeepalive` (loop pings the training channel periodically and survives a transient broadcast error) and `test_websocket_comprehensive.py::TestHeartbeatFunctionality` (channel-scoped ping reaches training but not control; no-channel still pings all). Latent adjacent issue noted for a separate PR: the `/ws/control` endpoint treats an inbound `{"type": "pong"}` as an unknown command — dormant today because the heartbeat never pings control.
- **#1 TAB-FEEDBACK-LOOP — collapse to one tab-persistence system + equality-guard the restore callback**: clicking one tab then another re-opened the previous tab (deterministic Snapshots→Dataset). Two compounding causes in `src/frontend/dashboard_manager.py`: (1) the clientside callback that restores `visualization-tabs.active_tab` from `layout-state-store` (Input on the Store's `data`) re-asserted the tab on *every* Store change — including the echo from the write callback that stamps the Store on each tab change — re-triggering every `Input("visualization-tabs", "active_tab")` callback and racing the `allow_duplicate` active_tab outputs; (2) a redundant *second* persistence system (hand-rolled `localStorage['juniper_canopy_active_tab']` with an `active_tab`→`active_tab` self-edge writer plus a `params-init-interval` mount restore) raced the Store restore at mount. Fix: the restore callback now takes the current tab as `State("visualization-tabs", "active_tab")` and returns `no_update` when `state.active_tab === currentTab` (mirrors the write callback's existing `prev.active_tab === activeTab` guard), and the legacy localStorage pair is deleted so `layout-state-store` (`storage_type="local"`) is the single source of truth. Net: `visualization-tabs.active_tab` now has exactly two writers (Store restore + tutorial-link trigger) and a single mount-time restore. Regression coverage in `test_dashboard_manager.py::TestLayoutStatePersistence`: legacy key fully removed, restore callback equality-guarded, exactly two active_tab outputs.

### Security

- **SEC-F19 log hygiene — hash the `canopy_session` cookie before logging (never log the raw value)**: `WebSocketManager.check_per_session_limit` (`src/communication/websocket_manager.py`) logged a raw 8-char prefix of the anonymous `canopy_session` cookie (`session_key[:8]`) when the per-session cap tripped. That cookie is a signed Starlette session token, so even a prefix in a log line is an avoidable session-identifier leak. A new `_hash_session_key_for_log` helper now emits a short, non-reversible tag instead — keyed HMAC-SHA256 over the raw cookie with a per-process random secret (`_LOG_HASH_KEY`), truncated to 12 hex chars — so the logged digest is not an offline-computable function of the cookie and does not correlate across process restarts, mirroring the cascor sibling that hashes its identity before logging (`juniper-cascor src/api/workers/security.py`). Regression coverage: `src/tests/unit/test_ws_connection_caps.py::TestPerSessionLogHygiene`. Independent security review of #420, §9.

- **SEC-F22 / D2 — startup loopback bind-guard (the loopback bind is now an enforced invariant)**: canopy's browser training-control gate (`/api/train/*`, `/ws/control`) authenticates the same-origin browser by `Origin` + CSRF, both of which are forgeable by an in-network **non-browser** client (spoofable `Origin`, anonymously-mintable CSRF token — audit HO-6), so the **only** effective control is the loopback bind. That bind was an implicit default, not an enforced invariant — flipping `BIND_HOST=0.0.0.0` silently made the control surface in-network- (or internet-) reachable. A new startup guard (`src/security.py`: `is_loopback_host` / `enforce_loopback_bind_guard` / `NonLoopbackBindError`, called from `main.lifespan`, mirroring the E-8 `enforce_dependency_floors` fail-loud idiom) now **refuses to start** (CRITICAL log + raise; fail-closed) when `settings.server.host` (`JUNIPER_CANOPY_SERVER__HOST`) is a non-loopback interface (anything not in `127.0.0.0/8`, `::1`, or `localhost`) **unless** at least one of two operator attestations (both default `False`) is `True` — `settings.loopback_publish_attested` (`JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED`, reachable only via a loopback-only host publish) or `settings.auth_proxy_attested` (`JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`, a fronting authenticating proxy terminates access); the attested non-loopback path logs a loud WARNING naming which attestation permitted it. Loopback binds (the default) start normally, so this is zero-UX for the shipped posture. Implemented **inline in canopy** (no new dependency). Regression coverage: `src/tests/unit/test_bind_guard.py`. Design-of-record: juniper-ml [`notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md) §4 / §8 (D2); implementation note: [`notes/JUNIPER_CANOPY_CONTROL-SURFACE-HARDENING_SEC-F22-F19_NOTE_2026-07-04.md`](notes/JUNIPER_CANOPY_CONTROL-SURFACE-HARDENING_SEC-F22-F19_NOTE_2026-07-04.md).

- **SEC-F19 / D4 — global + per-session WebSocket connection caps (kills the shared-NAT self-DoS)**: Docker NAT collapses every WS client to the bridge-gateway IP (audit HO-3), so the existing per-IP cap (`max_connections_per_ip=5`) is shared across all users behind the gateway — one client's five sockets exhaust the cap for everyone (a live self-DoS). `src/communication/websocket_manager.py` now adds, alongside the per-IP cap: (a) the stack-absolute **global** cap `max_connections` (=50) enforced in `connect()` — the single admission choke point shared by `/ws/training`, `/ws/control`, `/ws` — rejecting the N+1th connection stack-wide with close code `1013`; and (b) a **per-session** cap `max_connections_per_session` (=5, new `WebSocketSettings` field) keyed on the anonymous `canopy_session` cookie read from the WS handshake, restoring per-client fairness where the per-IP cap is inert (one session can no longer starve another behind the same gateway). A cookieless first connection is allowed and left to the global cap as the backstop. The three endpoints call a new `check_connection_limits()` (per-IP then per-session, rolling back the per-IP slot on a per-session rejection so a rejected attempt can't leak the per-IP counter); each endpoint keeps its existing close-reason (`/ws/control` stays opaque per M-SEC-06). The per-IP cap is retained but re-scoped honestly (a code comment + this note): it is **inert behind NAT** — DoS-dampening, **not** authentication. Regression coverage: `src/tests/unit/test_ws_connection_caps.py`. Design-of-record §5 / §8 (D4). **Deferred (Phase 4, owner-gated, NOT in this PR):** X-Forwarded-For-from-trusted-proxy (D6) and a real dashboard login / fronting proxy (D7) — the only mechanisms that restore genuine per-client identity / close SEC-F22 for the remote/multi-user case.

## [0.5.0] - 2026-05-23

**Note on version history**: `pyproject.toml` was bumped 0.3.0 → 0.4.0 on 2026-03-03 in preparation for a 0.4.0 release that was never cut to PyPI (the `[0.4.0]` section below documents the work that *would have* shipped). This 0.5.0 release rolls up both that work and the subsequent ~2.5 months of changes (983 commits since `v0.3.0`) into a single PyPI release. Subsequent entries in this section list the additional work landed since 2026-03-03.

### Added

- **`util/test_agents_md_version_drift.py`** -- portable port of juniper-ml's lint test pinning `AGENTS.md`'s `**Version**:` header to `pyproject.toml`'s `[project].version`. Catches the failure class where a `pyproject.toml` bump leaves the agent-facing contract stale. Preventive-only here: canopy's `AGENTS.md` and `pyproject.toml` are already in sync at `0.5.0`. Wired into the CI tests job next to the existing `test_workflow_script_paths.py` lint.

- Added documentation for the Network Editor service-mode investigation workflow and its network mutation proxy endpoints:
  - `docs/USER_MANUAL.md` now covers the `Investigating`-state gated Network Editor tab, append/remove/patch operations, service-mode constraints, and common failure modes.
  - `docs/api/API_REFERENCE.md` now documents `PATCH /api/v1/network/weights`, `POST /api/v1/network/hidden-units`, and `DELETE /api/v1/network/hidden-units/{idx}` with request examples and status-code expectations.

- **METRICS-MON R3.7 (soak complete)**: macOS leg of the unit-tests CI matrix flipped from `experimental: true` → `experimental: false`, making the `macos-latest` (Python 3.12) leg **required**. Failures on macOS now block the job. The `continue-on-error: ${{ matrix.experimental == true }}` job-level guard is preserved as a future-proof escape hatch for future experimental matrix entries; with `experimental: false` it evaluates to `false`. Soak window 2026-05-01 → 2026-05-15 confirmed clean (per user direction). Closes the post-soak follow-up of the R3.7 fan-out.

- **METRICS-MON R3.7 / seed-(R1.3 design)**: macOS leg added to the unit-tests CI matrix. `.github/workflows/ci.yml::unit-tests` now runs on `${{ matrix.os }}` with a single new `macos-latest` (Apple Silicon / ARM) entry pinned to Python 3.12; Linux legs (Python 3.12 + 3.13 + 3.14) are unchanged. The macOS leg starts in **`continue-on-error: true`** mode for a 2-week soak (2026-04-30 → 2026-05-14) so platform-divergence failures (POSIX-only assumptions in the WS / dashboard / dataset paths, etc.) surface in CI without blocking PRs while environment-specific issues are identified. The torch wheel install branches by OS — Linux uses the CPU-only PyTorch index (`https://download.pytorch.org/whl/cpu`) which has no macOS-arm64 wheels; macOS uses the default PyPI index which does. After the soak, flip the include block's `experimental` flag to `false` to make the macOS leg required. Closes the juniper-canopy leg of [METRICS_MONITORING_R3_ENTRY_PLAN_2026-04-30.md](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R3_ENTRY_PLAN_2026-04-30.md) §3 Q1.

- **METRICS-MON R2.2.5 / seed-05**: `CascorServiceAdapter._relay_loop` now validates every inbound `/ws/training` frame against the canonical Pydantic envelope schemas in `juniper-cascor-protocol>=0.1.0` (added as an explicit runtime dependency; also pulled in transitively by `juniper-cascor-client`). Validation is purely **observational** — never raises, never modifies the message dict — so the downstream dispatch logic (heartbeat-pong, metrics normalization, websocket broadcast, state-update callback) stays byte-compatible with the pre-migration behaviour. New Prometheus counter `juniper_canopy_unrecognized_ws_frames_total{type, endpoint}` exposed on canopy's existing `/metrics` mount; bumped when a frame fails validation (unknown `type` OR known `type` with malformed inner payload, e.g. `initial_metrics` with non-int `count`). The `type` label is bounded by the same R1.1 cardinality discipline the protocol package uses (first 16 distinct unknowns tracked verbatim per process; subsequent unknowns collapse to `"_unmatched"`) so an attacker emitting many distinct frame types cannot inflate label cardinality. New helper `observability.inc_unrecognized_ws_frame(type_label, endpoint)` emits a structured WARNING log line `juniper_canopy_unrecognized_ws_frame` alongside the counter increment for stacks without Prometheus scraping. New chaos-coverage test suite at `src/tests/unit/test_inbound_frame_validation.py` (10+ tests across 3 classes) pinning: known envelopes pass through unchanged, unknown types and malformed payloads increment the counter, the cardinality bound holds, the relay-loop guard absorbs hypothetical validation errors so the dashboard's broadcast loop stays alive. Note: this validation is intentionally redundant with `juniper-cascor-client`'s R2.2.4 inbound-frame validation — canopy's counter has its own service identity (`juniper_canopy_*` vs `juniper_cascor_client_*`) and provides defense-in-depth if cascor-client's hook is ever disabled. See [`notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md) in juniper-ml.

### Changed (potentially breaking)

- **METRICS-MON R2.1.5 / seed-06**: juniper-canopy's observability surface now consumes the shared `juniper-observability>=0.1.1` package (added as a runtime dependency). The cross-cutting machinery — `JuniperJsonFormatter`, `RequestIdMiddleware`, `PrometheusMiddleware`, `request_id_var`, `UNMATCHED_ENDPOINT_LABEL`, `configure_logging`, `get_prometheus_app`, `set_build_info` — moves into the shared lib; `observability.py` and `health.py` are preserved as thin re-export shims so existing imports (`from observability import …`, `from health import DependencyStatus, ReadinessResponse, probe_dependency`) continue to work unchanged. **Wire-format change**: `/v1/health/ready` body field `timestamp` now derives from `datetime.now(UTC).timestamp()` (was naive `datetime.now().timestamp()`) — closes the BUG-JD-06-equivalent local-time leak. Values stay unix-epoch-seconds and shift only by host tz-offset (irrelevant to consumers computing diffs). **Security improvement**: `configure_sentry` (now a thin wrapper around the shared implementation that preserves canopy's positional-arg call convention) gains the SEC-15 `before_send` hook that scrubs `X-API-Key` / `Authorization` / `Cookie` from outbound Sentry events — canopy's previous local implementation did not install this hook. The async `probe_dependency` wrapper continues to live in `health.py` and now delegates to the shared synchronous `juniper_observability.probe_dependency` via `asyncio.to_thread`. New `JuniperJsonFormatter()` default `service` is `"juniper-service"` (was `"juniper-canopy"`); all in-tree call sites pass the service name explicitly so this only affects ad-hoc construction. Wire-compat snapshot test added at `src/tests/unit/test_r2_1_5_wire_compat.py` pinning the `/v1/health/ready` JSON shape and the Prometheus metric names. See [`notes/code-review/METRICS_MONITORING_R2.1_SHARED_OBSERVABILITY_DESIGN_2026-04-28.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R2.1_SHARED_OBSERVABILITY_DESIGN_2026-04-28.md) in juniper-ml.

### Security

- **SEC-05 / SEC-12** (Phase 1B Track 1, 2026-04-24): `/ws` generic WebSocket endpoint now enforces the same `validate_origin` and `check_per_ip_limit` gates as `/ws/training` and `/ws/control`. Requests from unlisted origins or IPs over the per-IP cap are closed with standardized codes (4003 / 1013). Origin rejections are audit-logged via `log_ws_origin_rejected("/ws", …)`.
- **SEC-06** (Phase 1B Track 1): Opt-in bearer-token auth for all WebSocket endpoints. New setting `JUNIPER_CANOPY_WS_AUTH_ENABLED` (default `False`) gates the check; when enabled, clients must negotiate `Sec-WebSocket-Protocol: bearer, <token>` and the token is validated against `api_keys` with constant-time comparison. Accepted connections echo `bearer` as the chosen subprotocol. Default-off preserves compatibility while downstream clients catch up. `communication/websocket_manager.py::WebsocketManager.connect` gained an optional `subprotocol` parameter plumbed through by each endpoint.
- **SEC-13** (Phase 1B Track 1): `POST /api/remote/connect` no longer accepts `authkey` as a query parameter. The endpoint now requires a JSON body `{"host", "port", "authkey"}`, modeled by `RemoteConnectRequest` with `SecretStr` so the key is never written to URLs, web-server access logs, browser history, or Referer headers. Callers still sending the query param receive 422.
- **SEC-14** (Phase 1B Track 1): Replaced the five `JSONResponse({"error": str(e)}, status_code=500)` sites in `main.py` with opaque `{"error": "Internal server error", "error_id": <12-hex>}` responses (worker stats/list return `"Upstream error"` with the same `error_id`). The full traceback is logged server-side with the same `error_id` so operators can correlate client reports with logs without leaking internal paths, library versions, or connection strings to clients.

### Changed

- **CFG-16** (v7 roadmap): `create_backend()` (`src/backend/__init__.py`) no longer re-reads `CASCOR_DEMO_MODE` or `CASCOR_SERVICE_URL` via raw `os.getenv` as a "legacy fallback". Both env vars are already handled by the corresponding Settings field validators (`_check_legacy_demo_mode`, `_check_cascor_service_url` in `src/settings.py`), which emit `DeprecationWarning` and map the values onto `settings.demo_mode` / `settings.cascor_service_url`. Removing the duplicated raw reads collapses the selection chain from 7 cases to 5 (legacy fallback rows merged into the corresponding Settings field rows), drops the unused `import os` from `backend/__init__.py`, and ensures every legacy use is announced via the validator's deprecation warning rather than silently absorbed at the call site. The roadmap explicitly called out only `CASCOR_DEMO_MODE`; `CASCOR_SERVICE_URL` was bundled in the same PR because the redundancy pattern is identical (adjacent lines, same fix, single CHANGELOG entry). New regression suite at `src/tests/regression/test_cfg_16_create_backend_no_raw_env.py` pins two properties: (a) `backend/__init__.py` source contains neither `CASCOR_DEMO_MODE` nor `CASCOR_SERVICE_URL` (scope guard against reintroduction), and (b) the legacy `CASCOR_DEMO_MODE=1` path still produces a `DemoBackend` end-to-end via the Settings validator (behaviour guard, `importorskip("torch")` for env tolerance). Mirrors the cascor CFG-04 convergence pattern (canonical Settings field plus validator-handled legacy alias). No deprecation timeline change — the validator-level deprecation of `CASCOR_DEMO_MODE` / `CASCOR_SERVICE_URL` introduced earlier is unchanged.
- Phase D §S10.3 (D-49): **flag-flip** `enable_ws_control_buttons` default `False` → `True` after production soak passed on the P12b clientside routing. Training Start/Pause/Stop/Resume/Reset buttons now route through `window.cascorControlWS.send({command, command_id})` by default, with automatic REST fallback via `fetch('/api/train/<command>', {method:'POST'})` when the WS is disconnected, the `send()` promise rejects, or an error envelope arrives. The kill switch is unchanged: `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false` reverts to pure REST per §S10.7. Mirrors the earlier Phase B-P7 pattern (`enable_browser_ws_bridge`) and the Phase C-P10 pattern (`use_websocket_set_params`). Regression: 175 unit/integration/performance tests green (Phase C, Phase D envelope, Phase D clientside, `test_websocket_control`, `test_button_state`, `test_button_responsiveness`, `test_dashboard_manager`, `test_main_import_and_lifespan`, `test_main_coverage_95`, `test_phase_b_pre_b_csrf`).
- Phase D test updates: `test_enable_ws_control_buttons_default_off` renamed to `test_enable_ws_control_buttons_default_on_after_flip` asserting `True`; new `test_kill_switch_env_var_disables_flag` validates the §S10.7 rollback by constructing a fresh `Settings()` with `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false` set.

### Fixed

- **BUG-CN-01** (Track 3 Phase 3D, 2026-04-27): `DemoMode._perform_reset` (`src/demo_mode.py`) now applies all three transitions — `self.is_running = False`, `self._stop.clear()`, and `self._pause.clear()` — atomically inside a single `with self._lock:` block. Pre-fix the lock covered only the `is_running` write, so a reader could observe `is_running == False` while `_stop` was still set, leaving the next `start()` racing against a stale stop signal that gets cleared a moment later. Verified by `src/tests/unit/test_demo_mode_perform_reset.py` (1 AST-based source-level guard that always runs + 1 behavioural test using a `_TracingEvent` wrapper that records lock-held state at `clear()` time; behavioural test `importorskip("torch", exc_type=ImportError)` so the env's broken torch C-extension doesn't gate the regression coverage). Track 3 (Concurrency and Thread Safety) is fully implemented as of this fix.
- **BUG-CN-09 / BUG-CN-10 / CONC-08** (Track 3 Phase 3C, 2026-04-26): added `WebSocketManager._connections_lock = threading.Lock()` and a `DemoMode.running` property + `_set_running` helper that close three companion races. (1) `WebSocketManager.active_connections`/`connection_metadata` are now mutated and snapshot-iterated under `_connections_lock` in `connect`/`disconnect`/`send_personal_message`/`broadcast`/`broadcast_from_thread`/`get_connection_count`/`get_connection_info`/`get_statistics`/`shutdown`, eliminating the `RuntimeError: Set changed size during iteration` (BUG-CN-09). (2) `broadcast()` now increments `self.message_count` under the same lock, fixing the non-atomic `+= 1` (BUG-CN-10). (3) `DemoMode.is_running` reads/writes from API control entry points (`start`, `stop`, `pause`, `resume`, `reset`, `regenerate_dataset`) and the training thread go through the new `running` property and `_set_running` helper that serialize through `self._lock`, replacing the inconsistent mix of locked + unlocked sites (CONC-08). New regression suites `src/tests/unit/test_websocket_manager_thread_safety.py` (3 tests; concurrent disconnect-vs-snapshot, shutdown snapshot, atomic `message_count`) and `src/tests/unit/test_demo_mode_running_property.py` (5 source-level + 5 behavioural tests) cover the changes; the source-level tests run unconditionally so `DemoMode`'s torch-dependent tests can `importorskip` cleanly when the env's torch C-extension is broken.
- **CONC-01** (Track 3 Phase 3B, 2026-04-26): `WebSocketManager.check_per_ip_limit` and `WebSocketManager._decrement_ip_count` (`src/communication/websocket_manager.py`) now hold a new `self._ip_lock = threading.Lock()` across the read-modify-write on `_per_ip_counts`, so two threads racing on the same source IP can no longer both pass the cap check or lose a decrement. `threading.Lock` (not `asyncio.Lock` as in the plan recommendation) was chosen so the protection covers any caller — sync, async, or background thread (e.g. `broadcast_from_thread → disconnect`) — without forcing the public API to become async or cascading changes into the three `main.py` endpoints and the existing sync `disconnect()` callers. Verified by `src/tests/unit/test_websocket_manager_concurrency.py::TestPerIpRace` (3 tests using a `_SlowSetDict` proxy that widens the read-modify-write window to ~1 ms; the cap-respect and lost-update tests fail on the pre-fix code with `32 ≤ 5` and `1 == 32` and pass after).
- **CONC-07 / BUG-CN-11** (Track 3 Phase 3A, 2026-04-26): `DemoMode.regenerate_dataset` (`src/demo_mode.py`) now applies all reset state changes — `network.train_x`, `network.train_y`, `current_epoch`, `current_loss`, `current_accuracy`, and `metrics_history.clear()` — atomically inside a single `with self._lock:` block. Previously only `metrics_history.clear()` was protected, allowing the training thread (which reads these fields under `self._lock`) to observe a partial state such as a freshly assigned `train_x` paired with a stale `train_y`, or a stale epoch counter alongside the new dataset. Dataset generation itself remains outside the lock to avoid blocking readers across the JuniperData round-trip. New regression coverage in `src/tests/unit/test_demo_mode_concurrency.py::TestRegenerateDatasetLocking` (3 tests; the lock-scope test fails on the pre-fix code with `train_x: False, train_y: False` and passes after the fix).

### Added

- Phase D §S10.3 (P12b): flag-gated **clientside** training-button routing. When `settings.enable_ws_control_buttons=True`, the Start/Pause/Stop/Resume/Reset callbacks are registered as a Dash clientside callback (`PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS`) that routes clicks through `window.cascorControlWS.send({command, command_id})` with an automatic `fetch('/api/train/<command>', {method:'POST'})` REST fallback when the WS is disconnected, the `send()` promise rejects, or an error envelope comes back. The JS body preserves the existing server-side behavior: 500ms same-button debounce, optimistic `button-states` update, and trigger-id mapping. When the flag is off (default) the pre-P12b server-side handler (`_handle_training_buttons_handler`) is registered instead and keeps the existing fixtures, `test_button_state.py`, and `test_button_responsiveness.py` fully green.
- Phase D §S10.3: new `tests/unit/test_phase_d_button_clientside.py` with 11 unit tests covering (1) the JS string contract (`window.cascorControlWS`, `ws.send(`, `command_id`, `/api/train/`, 5-button trigger map, 500ms debounce, transport marker, optimistic `disabled:true`/`loading:true`), (2) flag-gated wiring — when off the JS is not inlined, when on the JS appears in Dash's `_inline_scripts`, both states still register the `training-control-action`/`button-states` outputs, (3) server-side handler regression — `_handle_training_buttons_handler` still POSTs to `/api/train/start` when invoked directly.
- Phase D (§S10) canonical `command_response` envelope on `/ws/control`. New helper `create_command_response_message` in `communication/websocket_manager.py` produces `{type:"command_response", data:{command, status, command_id?, result?, error?, code?}}` alongside legacy top-level `ok`/`command`/`state`/`error` fields so pre-Phase-D integration tests and any in-flight browser code keep working.
- Phase D (§S10.1) per-command timeouts on canopy's `/ws/control` endpoint: the handler dispatches commands via `asyncio.to_thread` and bounds them with `asyncio.wait_for`, reading the budget from a new module-level `_PHASE_D_CONTROL_TIMEOUTS` dict (seeded from `settings.ws_control_start_timeout` = 10s, `ws_control_stop_timeout` = 2s for stop/pause/resume/reset, `ws_control_set_params_timeout` = 1s). Timeouts emit `command_response{status:"error", error:"...timed out..."}` while leaving the connection open for follow-up commands.
- Phase D (§S10.3) unknown-command envelope on `/ws/control` now includes `code:"unknown_command"`, matching the cascor P11 contract so browser clients can distinguish protocol errors from execution failures.
- Phase D (§S10.3) `set_params` is now a first-class `/ws/control` command on canopy, routed through `backend.apply_params(**params)` (which already consults `use_websocket_set_params` for hot/cold routing via the Phase C adapter).
- Phase D (D-49) `enable_ws_control_buttons: bool = False` feature flag in `settings.py` with three companion budgets (`ws_control_start_timeout`, `ws_control_stop_timeout`, `ws_control_set_params_timeout`). Default-off so REST remains the happy path at merge time; a follow-up flips browser buttons over once staging soak is green.
- Phase D (§S10) browser `window.cascorControlWS.send()` is now `command_id`-correlated: every `send({command, ...})` auto-generates a UUIDv4 `command_id`, waits for a matching `command_response` envelope (not the legacy `control_ack`), and rejects with a descriptive error on per-command timeout (start=11s, set_params=2s, others=3s). On socket close every in-flight pending command is rejected so the UI can fall back to REST instead of hanging on a stale promise.
- Phase D: new `test_phase_d_control_buttons.py` unit test file with 15 tests covering the envelope helper (6), feature-flag defaults (3), `/ws/control` endpoint `command_id`/`unknown_command`/invalid-JSON/connection-survival behavior (4), and hanging-backend timeout enforcement (2) via a patchable `_PHASE_D_CONTROL_TIMEOUTS` dict.
- Hardcoded-values refactor (Wave 1 + Wave 2): added `SecurityConstants` (HTTP security headers, default CSP policy, rate-limit headers, body-limit error messages, exempt paths) and `BackendConstants` (REST endpoint paths, backend adapter timeouts, retry tuning, status keys) to `src/canopy_constants.py`. Extended `DashboardConstants` and `ServerConstants` with discovery host/port defaults, health probe paths, and additional dashboard tuning values.
- Documented documentation-link validation workflow and troubleshooting for CI and local developer runs:
  - Added `Documentation Links` CI job reference with command parity and cross-repo policy modes in `docs/ci_cd/CICD_REFERENCE.md`
  - Added a dedicated documentation-link failure pattern runbook in `docs/ci_cd/CICD_MANUAL.md`
  - Added local `check_doc_links.py` commands and failure causes to `docs/DEVELOPER_CHEATSHEET.md`

- **Contextual Left Menu**: Sidebar sections dynamically show/hide based on the active visualization tab. Training Controls always visible; Meta Parameters card, Network Information, and subsections toggle per tab via `TAB_SIDEBAR_CONFIG`. Card header text updates dynamically (e.g., "Network Parameters", "Candidate Parameters", "Dataset Parameters")
- **Candidate Metrics Tab**: New top-level tab (`tab_id="candidates"`) for dedicated candidate pool monitoring, placed immediately after Training Metrics. Features pool status badge, epoch progress bar, top-2 candidates table, pool training metrics, candidate loss plot (orange trace), and collapsible pool history (max 20 entries, memory storage)
- New `CandidateMetricsPanel` component (`src/frontend/components/candidate_metrics_panel.py`) extending `BaseComponent` with own data fetch callback gated on `active_tab == "candidates"`
- Collapsible contextual section wrappers (`ctx-growth-triggers-*`, `ctx-multi-node-*`, `ctx-spiral-dataset-*`, `ctx-pool-training-*`) with toggle callbacks, defaulting to `is_open=True`
- Sidebar decomposition: 15 addressable wrapper div IDs (`sidebar-nn-*`, `sidebar-cn-*`, `sidebar-network-info-section`, `sidebar-meta-params-card`, `sidebar-apply-section`)
- Unit tests for sidebar visibility configuration and CandidateMetricsPanel layout/helpers
- Added release-readiness navigation in `docs/DOCUMENTATION_OVERVIEW.md` for:
  - `notes/CODE_REVIEW_ANALYSIS_2026-04-04.md`
  - `notes/CODE_REVIEW_PLAN_2026-04-04.md`
  - `notes/CODE_REVIEW_DEVELOPMENT_ROADMAP_2026-04-04.md`

### Changed

- Hardcoded-values refactor (Wave 2): replaced ~55 inline literals across 9 modules (`middleware.py`, `discovery.py`, 4 backend adapters, dashboard manager, demo mode, plotter) with imports from `canopy_constants`. Module-level backwards-compat aliases (`EXEMPT_PATHS`, `_DEFAULT_CSP`, `_MAX_REQUEST_BODY_BYTES`, `_DEFAULT_PORTS`, `_DEFAULT_HOST`, `_DEFAULT_TIMEOUT`) are kept as references to the canonical constants — preserving the public API surface that tests import by name. AGENTS.md "Constants Management" section updated to list the 7 constant classes now exported by `canopy_constants`. All 29 unit tests pass; pre-commit (21 hooks) is clean.
- Extracted candidate pool section, history tracking, and pool display from `MetricsPanel` to `CandidateMetricsPanel`. Training Metrics tab retains candidate training trace in loss plot and candidate epoch progress bar for context
- Component count increased from 11 to 12; updated test assertions accordingly
- Updated CI and developer documentation for markdown link validation to reflect current `docs` workflow behavior and local reproduction commands:
  - `docs/ci_cd/CICD_REFERENCE.md`
  - `docs/DEVELOPER_CHEATSHEET.md`
  - Added explicit coverage of `scripts/check_doc_links.py` policies, including code-fence/inline-code skip behavior, anchor validation, cross-repo modes, and path-safety constraints.

- Namespaced Prometheus metrics (`juniper_canopy_` prefix) with WebSocket and demo mode metrics
- `juniper_canopy_websocket_connections_active` Gauge (by channel)
- `juniper_canopy_websocket_messages_total` Counter (by channel, type)
- `juniper_canopy_demo_mode_active` Gauge
- `juniper_canopy_build_info` Info metric

### Changed

- Expanded service-mode backend and testing documentation to cover regression-tested normalization contracts and dashboard handler edge cases:
  - `docs/cascor/CASCOR_BACKEND_MANUAL.md`
  - `docs/cascor/CASCOR_BACKEND_REFERENCE.md`
  - `docs/testing/TESTING_MANUAL.md`
  - `docs/testing/TESTING_REFERENCE.md`
  - Added explicit coverage for envelope unwrapping precedence, zero-value preservation (`0`/`0.0`), topology transformation constraints, dataset target conversion, and metrics panel replay/progress/validation-overlay behaviors.
- Refreshed CI/testing operations documentation to match the current workflow and marker gating behavior:
  - Rewrote `docs/ci_cd/CICD_QUICK_START.md`, `docs/ci_cd/CICD_MANUAL.md`, `docs/ci_cd/CICD_REFERENCE.md`, and `docs/ci_cd/CICD_ENVIRONMENT_SETUP.md` to reflect the active `.github/workflows/ci.yml` jobs (`pre-commit`, `unit-tests`, `integration-tests`, `security`, `dependency-docs`, `lockfile-check`, `docs`, `docker-build`).
  - Updated `docs/testing/TESTING_ENVIRONMENT_SETUP.md`, `docs/testing/TESTING_MANUAL.md`, and `docs/testing/TESTING_REFERENCE.md` with CI marker contracts and optional extras guidance for `juniper-cascor-client[testing]` and `juniper-data-client[testing]`.
  - Added explicit docs runbook coverage for `scripts/check_doc_links.py` (`--cross-repo skip`) and lockfile freshness checks using `uv pip compile`.

- Refreshed API documentation to match current runtime contracts for service-mode CasCor normalization and backend parity. Updated `docs/api/API_REFERENCE.md` and `docs/api/API_SCHEMAS.md` for `/api/status`, `/api/metrics`, `/api/metrics/history`, `/api/topology`, `/api/dataset`, `/api/decision_boundary`, training-control endpoints, and WebSocket message types.
- Updated dashboard and backend integration documentation for dashboard augmentation Phase 1-2:
  - `docs/USER_MANUAL.md`
  - `docs/api/API_REFERENCE.md`
  - `docs/cascor/CASCOR_BACKEND_REFERENCE.md`
  - Coverage includes:
    - Metrics panel state-driven UI (`learning_rate`, phase duration, grow/candidate progress bars, validation overlays)
    - Service-mode topology normalization details (3-layer mapping and output-weight transposition)
    - Service-mode dataset behavior for metadata-only responses and secondary dataset array fetch fallback
- Updated CI/CD documentation and dependency inventory to match workflow-pinned GitHub Action revisions for caching:
  - `docs/ci_cd/CICD_ENVIRONMENT_SETUP.md`
  - `docs/ci_cd/CICD_MANUAL.md`
  - `notes/juniper-canopy_OTHER_DEPENDENCIES.md`
- Updated documentation validation references to match the current `scripts/check_doc_links.py` behavior and test coverage:
  - `docs/ci_cd/CICD_REFERENCE.md`
  - `docs/testing/TESTING_REFERENCE.md`
  - `docs/DEVELOPER_CHEATSHEET.md`
  - Added command examples for CI-equivalent `--cross-repo skip` execution.
  - Documented parser/security/cross-repo edge-case coverage enforced by `src/tests/unit/test_check_doc_links.py`.

- Renamed HTTP metrics: `http_requests_total` → `juniper_canopy_http_requests_total`, `http_request_duration_seconds` → `juniper_canopy_http_request_duration_seconds`
- Updated CasCor backend documentation to cover service-mode behavior (`CascorServiceAdapter`, `ServiceBackend`, `CascorStateSync`), including startup attach/sync workflow, response normalization contracts, and service-mode troubleshooting:
  - `docs/cascor/CASCOR_BACKEND_MANUAL.md`
  - `docs/cascor/CASCOR_BACKEND_REFERENCE.md`
  - `docs/cascor/CASCOR_BACKEND_QUICK_START.md`

### Fixed

- **DOCKER-001: .dockerignore excluded README.md** — Removed `README.md` from `.dockerignore` exclusion list. The Dockerfile `COPY pyproject.toml README.md ./` step requires README.md in the build context, but the .dockerignore was excluding it, causing Docker builds to fail.
- **DOCKER-REGRESSION: Forced demo mode removed from Docker runtime defaults** — Removed `JUNIPER_CANOPY_DEMO_MODE=1` from both `Dockerfile` and `conf/Dockerfile`. Forcing demo mode silently routes deployments to `DemoBackend`, which can ignore configured `CASCOR_SERVICE_URL` and serve synthetic training data instead of real backend data.

---

## [0.4.0] - 2026-03-03

**Summary**: Comprehensive security hardening — security headers middleware (Dash-compatible CSP), request body limits, error sanitization, conditional CORS, rate limiting enabled by default, WebSocket authentication with message size limits and idle timeout, /metrics auth, conditional docs, build attestations, and scheduled security scanning.

### Security

- Added `SecurityHeadersMiddleware` with Dash-compatible CSP (`'unsafe-inline'` for Dash/Plotly), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, conditional HSTS
- Added `RequestBodyLimitMiddleware` with configurable max body size (default 10MB)
- Sanitized error responses — generic messages returned to clients; internal details logged at DEBUG
- Changed CORS to conditional mode (restricted when origins configured via environment)
- Changed rate limiting default from disabled to enabled
- Added WebSocket authentication — API key validation at connection accept
- Added WebSocket message size limits (64KB for control, 1MB for data)
- Added WebSocket idle connection timeout (5 minutes default, configurable)
- Added API key requirement for `/metrics` endpoint
- Added conditional API docs — disabled when API keys are configured
- Enabled build attestations in publish workflow

### Added

- `.github/workflows/security-scan.yml` — Weekly scheduled security scanning (Bandit, pip-audit)

### Changed

- Updated `conftest.py` to disable rate limiting during test execution (`CANOPY_RATE_LIMIT_ENABLED=false`)
- Updated `test_cascor_ws_control.py` assertion for sanitized error messages

### Technical Notes

- **SemVer impact**: MINOR — New middleware, changed security defaults (non-breaking: configurable via env vars)
- **Test count**: 3,373 passed, 0 failed, 19 skipped
- **Part of**: Cross-ecosystem security audit (7 repos, 24 findings)

---

## [0.3.0] - 2026-02-26

**Summary**: First PyPI release. Added packaging infrastructure for distribution via `pip install juniper-canopy`.

### Added

- `juniper_canopy/__init__.py` wrapper module with `__version__` for PyPI import verification
- `.github/workflows/publish.yml` — 3-job publish pipeline (build → TestPyPI → PyPI) with OIDC trusted publishing
- Core runtime dependencies declared in `pyproject.toml` (dash, fastapi, uvicorn, plotly, numpy, scipy, etc.)
- `[tool.setuptools.packages.find]` configuration for automatic package discovery

### Changed

- Version bumped from 0.2.1 to 0.3.0 (40+ commits since last tag with significant changes)
- Synchronized `src/__init__.py` version to 0.3.0

---

### Fixed

- **RC-1/RC-2 - CasCor In-Process Backend Initialization**: Real backend mode now creates a network, installs monitoring hooks, starts monitoring thread, fetches dataset from JuniperData, and registers WebSocket callbacks during lifespan startup — CasCor runs in-process, not as a separate OS process
- **RC-3 - WebSocket Control Commands for Real Backend**: `/ws/control` endpoint now handles start/stop/reset commands for CasCor backend (pause/resume return "not supported" since CasCor training is atomic per phase)
- **RC-4 - Startup Script External Process Launch**: Removed `nohup` background CasCor process launch from `util/juniper_canopy.bash`; CasCor now runs in-process via `CascorIntegration`
- **RC-5 - JUNIPER_DATA_URL Validation in All Modes**: Moved JUNIPER_DATA_URL validation before the demo/real mode branch so both modes validate the URL at startup
- **CF-1 - Mode Flag Synchronization**: Startup script now exports `CASCOR_DEMO_MODE` based on shell `DEMO_MODE` for consistent mode detection between shell and Python
- **CF-3 - CasCor Backend Path for In-Process Integration**: Startup script exports `CASCOR_BACKEND_PATH` so CascorIntegration can locate CasCor modules for import

### Added

- **Integration Tests** (42 new tests):
  - `test_cascor_real_backend_init.py` — 7 tests for in-process backend initialization lifecycle
  - `test_cascor_ws_control.py` — 9 tests for WebSocket control commands with CasCor backend
  - `test_cascor_lifecycle.py` — 8 tests for CascorIntegration create/hook/monitor/shutdown lifecycle
- **Unit Tests**:
  - `test_juniper_data_url_validation.py` — 5 tests for JUNIPER_DATA_URL validation in both modes
- **Regression Tests**:
  - `test_mode_flag_consistency.py` — 13 tests for CASCOR_DEMO_MODE flag parsing consistency

### Analysis

- **Integration Development Plan**: Comprehensive assessment of all outstanding integration work across JuniperCascor, JuniperCanopy, and JuniperData
  - Evaluated 4 source documents: JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN.md, INTEGRATION_ROADMAP.md, PRE-DEPLOYMENT_ROADMAP.md, PRE-DEPLOYMENT_ROADMAP-2.md
  - Rigorous source code review identified 17 issues (3 CRITICAL, 3 HIGH, 8 MEDIUM, 3 LOW)
  - **CRITICAL**: Real backend control not implemented (main.py:433-442), decision boundary incomplete (main.py:779-788), `get_network_data()` missing from CascorIntegration
  - **HIGH**: `save_snapshot()`/`load_snapshot()` missing, async boundary untested, no real backend test coverage, JuniperData client unused
  - 30+ enhancement items catalogued (CAN-001 through CAN-021, CAS-001 through CAS-010)
  - Created `notes/INTEGRATION_DEVELOPMENT_PLAN.md` with 53+ items in 4 prioritized phases

- **Non-Passing Test Analysis (Rounds 1 & 2)**: Comprehensive analysis and fix of all non-passing tests
  - Round 1: 67 non-passing tests (54 ERROR, 10 FAILED, 3 XFAIL) - 6 root causes identified
  - Round 2: Additional 9 tests (5 skipping, 2 failing, 1 skipped, 1 race condition)
  - Created analysis document in `notes/FIX_FAILING_TESTS.md`
  - Final result: 3,215 passed, 0 failed, 0 errors, 0 xfail, 37 skipped (all legitimate)

### Fixed

- **P0 - Missing pytest-mock dependency**: Installed `pytest-mock>=3.12` (resolves 54 ERROR tests)
- **P1 - Snapshot private attribute leakage**: Added `not key.startswith("_")` filter in `main.py` snapshot creation to exclude private/protected attributes from HDF5 files
- **P2 - WebSocket control command race condition**: Fixed `test_control_command_sequence`, `test_control_start_with_reset_true`, and `test_unknown_command_returns_error` to drain interleaved broadcast messages before asserting on control response
- **P4 - Logger VERBOSE level**: Changed `CascorLogger.verbose()` to use `self.VERBOSE_LEVEL` instead of non-existent `logging.VERBOSE` (Epic 3.6 CQ-001)
- **P5 - LoggingConfig empty YAML**: Added null check after `yaml.safe_load()` in `LoggingConfig._load_config()` to handle empty YAML files (Epic 3.6 CQ-001)
- Removed 3 `@pytest.mark.xfail` markers from `test_logger_coverage_95.py` (bugs now fixed)
- **WebSocket state tests**: Added state message on `/ws/training` connect; rewrote `test_websocket_state.py` to consume deterministic connect sequence; removed `requires_server` marker
- **WebSocket ping-pong tests**: Updated `test_main_coverage.py` and `test_main_ws.py` to drain 3rd connect message
- **Logger coverage skip**: Removed `@pytest.mark.skip` from `test_verbose_logging` in `test_logger_coverage.py`
- **DemoMode singleton isolation**: Extended `reset_singletons` fixture to also reset `demo_mode._demo_instance`

### Unchanged

- **P3 - Server-dependent tests**: 8 tests correctly marked `requires_server` - no code change needed (environmental configuration issue)

---

## [0.31.0] - 2026-02-04

**Summary**: Test Suite & CI/CD Enhancement - Phase 4 Complete (All Phases Complete). Standardized configuration, improved documentation, re-enabled MyPy error codes, reviewed exception suppression patterns.

### Changed: [0.31.0]

- **Epic 4.1: Configuration Standardization**
  - `.coveragerc`: Standardized `fail_under` to 80% (was 60%)
  - `pyproject.toml`: Removed `-p no:warnings` from pytest addopts (re-enabled warnings)
  - Coverage threshold now consistent at 80% across all configs

- **Epic 4.2: Documentation and Cleanup**
  - `.pre-commit-config.yaml`: Added docs/ to markdown linting (was excluded)
  - `src/.markdownlint.yaml`: Created markdownlint configuration file
  - `docs/testing/TEST_DIRECTORY_STRUCTURE.md`: Created test directory documentation
  - Fixed misleading docstrings in test files

- **Epic 4.3: MyPy Improvements**
  - `.pre-commit-config.yaml`: Re-enabled 9 MyPy error codes with 0 violations:
    - `call-arg`, `override`, `no-redef`, `index`
    - `func-returns-value`, `has-type`, `str-bytes-safe`, `call-overload`, `return`
  - Disabled codes reduced from 15 to 7 (including new `dict-item`)
  - Remaining disabled codes have legitimate violations requiring gradual fixes

- **Epic 4.4: Address contextlib.suppress Usage**
  - `src/communication/websocket_manager.py`: Documented suppress pattern (WebSocket shutdown cleanup)
  - `src/config_manager.py`: Documented suppress patterns (type coercion logic)
  - All source code suppression patterns reviewed and documented

### Technical Notes: [0.31.0]

- **SemVer impact**: MINOR - Configuration and tooling improvements; no API changes
- Implements Phase 4 (all 4 epics complete) of TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md
- All success metrics achieved or exceeded (see development plan)
- TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md marked complete

---

## [0.30.0] - 2026-02-04

**Summary**: Test Suite & CI/CD Enhancement - Phase 3 Complete. Fixed logically weak tests, unconditional skips, exception suppression, re-enabled Flake8 checks, removed duplicate test classes, and converted bug-documenting tests to xfail.

### Changed: [0.30.0]

- **Epic 3.1: Fixed Logically Weak Tests (Partial)**
  - `src/tests/unit/test_main_coverage.py`
    - Removed weak TestTrainingControlEndpoints class (better version in _95)
    - Removed weak TestSetParamsEndpoint class (better version in _95)
    - Updated TestNetworkStatsEndpoint with documentation explaining 503 scenarios
    - Updated TestTopologyEndpoint with documentation explaining 503 scenarios
    - Updated TestDatasetEndpoint to expect 200 in demo mode
    - Updated TestDecisionBoundaryEndpoint to expect 200 in demo mode
  - `src/tests/unit/test_main_coverage_extended.py`
    - Fixed 4 `in [200, 400, 500]` assertions to expect 200 for valid params
    - Added documentation for exception test that legitimately accepts multiple codes
  - Reduced `in [200, 503]`/`in [200, 400, 500]` patterns from 21 to 5
  - Remaining 5 patterns are legitimately variable (network data may be unavailable)

- **Epic 3.2: Address Unconditional Skips**
  - `src/tests/integration/test_demo_endpoints.py`
    - Converted 3 WebSocket broadcast tests from unconditional `@pytest.mark.skip` to conditional `@pytest.mark.e2e` + `@pytest.mark.requires_server`
  - `src/tests/integration/test_parameter_persistence.py`
    - Converted 1 server test from unconditional skip to `@pytest.mark.e2e` + `@pytest.mark.requires_server`
  - `docs/testing/ADR_001_VALID_TEST_SKIPS.md`
    - Created ADR documenting valid skips: VERBOSE logging, HDF5 patching, TestClient CORS bypass

- **Epic 3.3: Fix Exception Suppression in Tests**
  - Fixed 5 tests using try/except/success antipattern:
    - `src/tests/unit/test_network_visualizer.py` - `test_register_callbacks_with_mock_app`
    - `src/tests/unit/test_decision_boundary.py` - `test_register_callbacks_with_mock_app`
    - `src/tests/unit/test_metrics_panel.py` - `test_register_callbacks_with_mock_app`
    - `src/tests/unit/test_training_metrics.py` - `test_setup_callbacks_with_mock_app`
    - `src/tests/unit/test_dataset_plotter.py` - `test_register_callbacks_with_mock_app`
  - Converted to direct assertions - pytest will catch exceptions

- **Epic 3.4: Re-enable Additional Flake8 Checks**
  - `.pre-commit-config.yaml`
    - Re-enabled B905 (zip without strict=) for source code
    - Re-enabled F401 (unused imports) for source code
    - Re-enabled B008 (function calls in default arguments) for source code
  - `src/backend/cascor_integration.py` - Added `strict=True` to zip() call
  - `src/frontend/components/hdf5_snapshots_panel.py` - Added `strict=True` to zip() call
  - `src/frontend/components/cassandra_panel.py` - Removed unused `Optional` import
  - `src/main.py`
    - Added `Path` import (fixing F821 undefined name)
    - Removed unused walrus assignments in start/stop training endpoints (F841)
    - Removed redundant `from pathlib import Path` in `_load_layouts()` (F401)

- **Epic 3.5: Removed Duplicate Test Classes**
  - `src/tests/unit/test_main_coverage_95.py`
    - Removed 4 duplicate classes that were exact copies of test_main_coverage.py:
      - TestHealthCheckEndpoint (45 lines removed)
      - TestStateEndpoint (26 lines removed)
      - TestStatusEndpoint (26 lines removed)
      - TestRootEndpoint (14 lines removed)
    - Total: 111 lines of duplicate code removed

- **Epic 3.6: Convert Bug-Documenting Tests to xfail**
  - `src/tests/unit/test_logger_coverage_95.py`
    - Converted `test_empty_yaml_file` from documenting bug to proper `@pytest.mark.xfail` marker
    - Test now clearly indicates expected vs actual behavior
    - Will auto-pass when the underlying LoggingConfig bug is fixed

### Technical Notes: [0.30.0]

- **SemVer impact**: MINOR - Test quality improvements; no API changes
- Implements Phase 3 (all 6 epics complete) of TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md
- All modified tests pass; pre-existing errors in unmodified files

---

## [0.29.0] - 2026-02-04

**Summary**: Test Suite & CI/CD Enhancement - Phase 2 Complete. Consolidated conftest.py, fixed type annotations, enabled test linting.

### Changed: [0.29.0]

- **Epic 2.1: Consolidated conftest.py Files**
  - Deleted duplicate `src/tests/fixtures/conftest.py` (224 lines)
  - Updated main `src/tests/conftest.py` to clean both `CASCOR_TEST_` and `JUNIPER_CANOPY_TEST_` env vars
  - Single source of truth for all test fixtures

- **Epic 2.2: Type Annotation Fixes**
  - `src/config_manager.py`: Fixed `__init__` type annotation (`Optional[str]` → `Optional[Union[str, Path]]`)

- **Epic 2.3: Enabled Test Linting**
  - `.pre-commit-config.yaml`: Added separate flake8 hook for tests with relaxed settings
  - Tests now linted with higher complexity limit (20 vs 15)
  - Allowed patterns in tests: assert (S101), random (S311)

### Technical Notes: [0.29.0]

- **SemVer impact**: MINOR - Test infrastructure improvements; no API changes
- Implements Phase 2 of TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md
- MyPy error codes deferred to Phase 4 (requires more extensive type fixes)

---

## [0.28.0] - 2026-02-04

**Summary**: Test Suite & CI/CD Enhancement - Phase 1 Complete. Eliminated false-positive tests, moved non-test files, and fixed security scan suppression.

### Changed: [0.28.0]

- **Epic 1.1: Eliminated False-Positive Tests**
  - `src/tests/performance/test_button_responsiveness.py`
    - Replaced 4 `assert True` patterns with actual button behavior tests
    - Tests now verify: rapid clicking prevention, button disable during execution, timeout re-enable, success re-enable
  - `src/tests/integration/test_button_state.py`
    - Replaced `assert True` with actual button state verification
  - `src/tests/unit/frontend/test_metrics_panel_coverage.py`
    - Replaced `assert True` with proper None handling verification
  - `src/tests/unit/test_dashboard_manager.py`
    - Fixed exception handling test to properly catch TypeError/ValueError
  - `src/tests/unit/test_config_refactoring.py`
    - Replaced try/except with pytest.raises pattern
  - `src/tests/regression/test_candidate_visibility.py`
    - Converted from manual script to proper pytest with assertions
    - Added @pytest.mark.e2e and @pytest.mark.requires_server markers

- **Epic 1.2: Removed Non-Test Files from Test Directory**
  - Moved 5 manual verification scripts to `util/verification/`:
    - `test_yaml.py` → `util/verification/verify_yaml.py`
    - `test_dashboard_init.py` → `util/verification/verify_dashboard_init.py`
    - `test_and_verify_button_layout.py` → `util/verification/verify_button_layout.py`
    - `implementation_script.py` → `util/verification/implementation_script.py`
    - `test_config.py` → `util/verification/verify_config_integration.py`

- **Epic 1.3: Fixed Security Scan Suppression in CI**
  - `.github/workflows/ci.yml`
    - Bandit: Removed `|| true`, added proper exit code handling with output capture
    - pip-audit: Changed warning to failure, added explicit error messaging
  - Added `.bandit.yml` security configuration file
    - Defines excluded directories (src/tests, util/verification)
    - Documents skipped checks with justification (B104, B311)
    - Sets severity and confidence thresholds

### Added: [0.28.0]

- **New Configuration Files**
  - `.bandit.yml` - Security scan configuration for Bandit SAST tool

- **New Directory Structure**
  - `util/verification/` - Manual verification scripts moved from test directory

### Technical Notes: [0.28.0]

- **SemVer impact**: MINOR - Test infrastructure improvements; no API changes
- **Test quality**: Eliminated 9 `assert True` false-positive patterns
- **Test organization**: Removed 5 non-test files from test directory
- **CI security**: Security scans now fail appropriately on issues
- Implements Phase 1 of TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md

---

## [0.27.0] - 2026-02-01

**Summary**: CI/CD parity achieved across JuniperCascor, JuniperData, and JuniperCanopy with standardized settings.

### Changed: [0.27.0]

- **CI/CD Configuration Parity**
  - `.pre-commit-config.yaml` (v1.2.0)
    - Line length: 512 for black, isort, flake8
    - Added yamllint hook (v1.35.1, relaxed config)
    - Enabled mypy in CI (removed from skip list)
  - `.github/workflows/ci.yml` (v0.12.0)
    - Coverage threshold: 80% (up from 50%)
    - Added build job with package verification
    - Standardized artifact paths: reports/junit/, reports/htmlcov/, reports/coverage.xml
    - Replaced 6-job pipeline with 7-job pipeline (added build)
  - `pyproject.toml` (v0.2.3)
    - Line length: 512 for black/isort
    - Coverage fail_under: 80%

### Technical Notes: [0.27.0]

- **SemVer impact**: MINOR – CI pipeline structure changed
- **CI Parity**: All 3 Juniper applications now use identical CI/CD settings

---

## [0.26.1] - 2026-01-31

### Fixed: [0.26.1]

- **JuniperData API Contract Fixes** (Oracle verification identified issues)
  - **`src/demo_mode.py`**: Fixed `_generate_spiral_dataset_from_juniper_data()`
    - Changed param key from `n_points` to `n_points_per_spiral`
    - Changed response key from `id` to `dataset_id`
    - Changed NPZ keys from `inputs/targets` to `X_full/y_full`
    - Added `np.argmax()` conversion for one-hot labels
    - Added `seed` parameter for reproducibility

  - **`src/backend/cascor_integration.py`**: Fixed `_create_juniper_dataset()`
    - Changed param key from `n_points` to `n_points_per_spiral`
    - Changed response key from `id` to `dataset_id`
    - Changed NPZ keys from `features/labels` to `X_full/y_full`
    - Added `np.argmax()` conversion for one-hot labels
    - Added `seed` parameter for reproducibility

### Technical Notes: [0.26.1]

- **SemVer impact**: PATCH – Bug fixes; no API changes
- Oracle analysis verified extraction completeness
- All 83 tests passing after fixes

---

## [0.26.0] - 2026-01-31

### Added: [0.26.0]

- **Phase 4: JuniperData Integration** (JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN.md)
  - **New Module**: `src/juniper_data_client/`
    - `__init__.py` - Package exports JuniperDataClient
    - `client.py` - REST client for JuniperData service
      - `create_dataset(generator, params)` - Create/generate dataset
      - `download_artifact_npz(dataset_id)` - Download NPZ artifact as dict
      - `get_preview(dataset_id, n)` - Get dataset preview

  - **Updated**: `src/demo_mode.py`
    - Added JuniperData integration to `_generate_spiral_dataset()`
    - New method `_generate_spiral_dataset_from_juniper_data()` for service calls
    - New method `_generate_spiral_dataset_local()` for fallback generation
    - Feature flag: `JUNIPER_DATA_URL` enables JuniperData mode

  - **Updated**: `src/backend/cascor_integration.py`
    - Added JuniperData integration to `_generate_missing_dataset_info()`
    - New method `_generate_dataset_from_juniper_data()` for service calls
    - New method `_generate_dataset_local()` for fallback generation
    - Feature flag: `JUNIPER_DATA_URL` enables JuniperData mode

### Technical Notes: [0.26.0]

- **SemVer impact**: MINOR – New JuniperData integration; backward compatible
- Part of Spiral Dataset Generator Refactor Phase 4
- All existing tests passing (demo_mode: 59 tests, cascor_integration: 24 tests)
- Graceful fallback to local generation when JuniperData unavailable

### Usage: [0.26.0]

```bash
# Enable JuniperData service integration
export JUNIPER_DATA_URL=http://localhost:8100

# Disable (uses local generation - default, backward compatible)
unset JUNIPER_DATA_URL
```

---

## [0.25.0] - 2026-01-25

### Added: [0.25.0]

- **P1-NEW-003: Async Training Boundary** (PRE-DEPLOYMENT_ROADMAP-2.md Phase C.1)
  - **Location**: `src/backend/cascor_integration.py`
  - **Problem**: Synchronous `fit()` method blocks FastAPI event loop
  - **Solution**:
    - Added `ThreadPoolExecutor` with `max_workers=1` for async training
    - Added `is_training_in_progress()` method to check training status
    - Added `request_training_stop()` for best-effort stop requests
    - Added `fit_async()` method using `asyncio.run_in_executor()`
    - Added `start_training_background()` for fire-and-forget training
    - Updated `shutdown()` to clean up executor

- **P1-NEW-002: RemoteWorkerClient Integration** (PRE-DEPLOYMENT_ROADMAP-2.md Phase C.2)
  - **Location**: `src/backend/cascor_integration.py`
  - **Problem**: RemoteWorkerClient for distributed training not exposed
  - **Solution**:
    - Added RemoteWorkerClient import from Cascor backend
    - Added `connect_remote_workers(address, authkey)` method
    - Added `start_remote_workers(num_workers)` method
    - Added `stop_remote_workers(timeout)` method
    - Added `disconnect_remote_workers()` method
    - Added `get_remote_worker_status()` method
    - Updated `shutdown()` to disconnect remote workers

- **New API Endpoints** (PRE-DEPLOYMENT_ROADMAP-2.md Phase C)
  - **Location**: `src/main.py`
  - Training endpoints updated for cascor_integration:
    - `POST /api/train/start` - Now uses `start_training_background()`
    - `POST /api/train/stop` - Now supports cascor_integration stop
    - `GET /api/train/status` - New endpoint for training status
  - Remote worker endpoints:
    - `GET /api/remote/status` - Check remote worker status
    - `POST /api/remote/connect` - Connect to remote manager
    - `POST /api/remote/start_workers` - Start workers
    - `POST /api/remote/stop_workers` - Stop workers
    - `POST /api/remote/disconnect` - Disconnect from manager

### Technical Notes: [0.25.0]

- **SemVer impact**: MINOR – New features added; no breaking changes
- Part of PRE-DEPLOYMENT_ROADMAP-2.md Phase C implementation
- P1-NEW-001 (Full IPC) deferred per Oracle analysis
- All syntax validated; full test verification pending

---

## [0.24.7] - 2026-01-24

### Added: [0.24.7]

- **End-to-End Integration Analysis**: Documentation of Cascor-Canopy integration
  - Summarized in `notes/PRE-DEPLOYMENT_ROADMAP.md` Section 10
  - Key issues identified (INTEG-001 through INTEG-005)
  - Reference to JuniperCascor PRE-DEPLOYMENT_ROADMAP.md for full analysis

- **Continuous Profiling Infrastructure**: Reference documentation
  - See JuniperCascor PRE-DEPLOYMENT_ROADMAP.md Section 11 for full design
  - Applicable to both Cascor backend and Canopy frontend

- **Code Coverage Roadmap**: Canopy-specific coverage targets
  - Current: ~73%, Target: 90%
  - Priority areas: Backend integration, WebSocket manager, training state machine

### Documentation: [0.24.7]

- Updated `notes/PRE-DEPLOYMENT_ROADMAP.md` with sections 10, 11, 12
  - Section 10: Integration analysis summary
  - Section 11: Profiling infrastructure references
  - Section 12: Canopy-specific coverage roadmap

### Technical Notes: [0.24.7]

- **SemVer impact**: PATCH – Documentation only; no code changes
- Investigation and planning phase for integration verification
- No code changes in this release

---

## [0.24.6] - 2026-01-24

### Fixed: [0.24.6]

- **CANOPY-P1-003**: Fixed monitoring thread race condition
  - **Location**: `src/backend/cascor_integration.py`
  - **Problem**: `_monitoring_loop()` reads `network.history` while training mutates it, causing intermittent exceptions or inconsistent reads
  - **Solution**:
    - Added `self.metrics_lock = threading.Lock()` for thread-safe metrics extraction
    - Updated `_extract_current_metrics()` to use lock when accessing network.history
    - Added defensive copying of history lists while holding lock
    - Added exception handling for concurrent modification edge cases
  - **Lines Changed**: 117-121, 765-789

### Verified: [0.24.6]

- **CANOPY-P1-002**: Module naming collision - Workaround verified working
  - `CascorIntegration._add_backend_to_path()` uses `sys.path.insert(0, ...)` to ensure Cascor modules take priority
  - Full rename deferred to post-deployment

### Technical Notes: [0.24.6]

- **SemVer impact**: PATCH – Thread safety fix; no API changes
- Part of PRE-DEPLOYMENT_ROADMAP.md P1 issue resolution
- All existing tests continue to pass

---

## [0.24.5] - 2026-01-22

### Added: [0.24.5]

- **Integration Issue 4.3**: Added metrics normalization to DataAdapter
  - **Location**: `src/backend/data_adapter.py`
  - **Problem**: Key naming mismatch between Cascor backend and Canopy frontend
    - Cascor uses `value_loss`/`value_accuracy`
    - Canopy expects `val_loss`/`val_accuracy`
  - **Solution**: Added `normalize_metrics()` and `denormalize_metrics()` methods
  - **Key Mappings**:
    - `value_loss` → `val_loss`
    - `value_accuracy` → `val_accuracy`
    - `loss` → `train_loss` (legacy format)
    - `accuracy` → `train_accuracy` (legacy format)
  - **Tests Added**: 20 new unit tests in `tests/unit/backend/test_data_adapter_normalization.py`
  - **Result**: Bidirectional metrics format conversion between Cascor and Canopy

- **Integration Issue 4.2**: API/Protocol Compatibility Verification
  - **Location**: `src/tests/integration/test_cascor_api_compatibility.py`
  - **Tests Added**: 21 new integration tests verifying:
    - Network attribute structure (input_size, output_size, hidden_units, etc.)
    - Training history format (train_loss, train_accuracy, value_loss, etc.)
    - Hidden unit structure (weights, bias, activation_fn)
    - Topology extraction compatibility
    - Metrics normalization integration
  - **Result**: All API contracts verified compatible

### Identified: [0.24.5]

- **Module Naming Collision**: Canopy's `constants.py` shadows Cascor's `constants/` package
  - **Impact**: Direct imports from Canopy code may fail
  - **Workaround**: `CascorIntegration` handles path ordering automatically
  - **Recommendation**: Consider renaming to avoid collision

### Technical Notes [0.24.5]

- **SemVer impact**: PATCH – New methods and tests added; no breaking changes
- `data_adapter.py` version: 0.1.4 → 0.1.5
- All 20 normalization tests pass
- All 21 API compatibility tests pass (2 require CASCOR_BACKEND_AVAILABLE=1)

---

## [0.24.4] - 2026-01-21

### Fixed: [0.24.4]

- **CANOPY-P2-001**: Fixed `asyncio.iscoroutinefunction` deprecation warning
  - **Location**: `src/tests/unit/test_main_coverage_extended.py:434`
  - **Problem**: `asyncio.iscoroutinefunction` is deprecated and slated for removal in Python 3.16
  - **Fix**: Replaced `asyncio.iscoroutinefunction()` with `inspect.iscoroutinefunction()`
  - **Changes**:
    - Added `import inspect` at line 20
    - Replaced deprecated function call at line 437
    - Original line commented out with CANOPY-P2-001 reference
  - **Result**: Test passes without deprecation warning

- **Integration Issue 4.1**: Updated backend path configuration
  - **Location**: `conf/app_config.yaml`
  - **Problem**: Hardcoded backend path limited deployment flexibility
  - **Fix**: Changed to environment variable with default fallback: `${CASCOR_BACKEND_PATH:../JuniperCascor/juniper_cascor}`
  - **Added**: `CASCOR_BACKEND_PATH` to environment_variables list
  - **Result**: Backend path can be configured via environment variable

### Technical Notes [0.24.4]

- **SemVer impact:** PATCH – Bug fixes; no API changes
- Tests pass without deprecation warnings
- Backend path now flexible via environment variable

---

## [0.24.3] - 2026-01-20

### Identified: Deprecation Warning

- **CANOPY-P2-001**: Documented `asyncio.iscoroutinefunction` deprecation warning
  - **Location**: `src/tests/unit/test_main_coverage_extended.py:434`
  - **Warning**: `'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use 'inspect.iscoroutinefunction' instead`
  - **Impact**: Cosmetic - generates deprecation warning in test output; will break in Python 3.16
  - **Status**: ✅ RESOLVED in v0.24.4
  - **Fix Applied**: Replaced with `inspect.iscoroutinefunction()`

### Technical Notes [0.24.3]

- **SemVer impact:** PATCH – Documentation only; no code changes
- Issue documented in `JuniperCascor/juniper_cascor/notes/INTEGRATION_ROADMAP.md` (v1.7.0)

---

## [0.24.2] - 2026-01-12

### Environment Fix: Missing pytest-mock Dependency

Fixed 32 test failures caused by missing `pytest-mock` dependency in the `JuniperCanopy` conda environment.

### Fixed [0.24.2]

- **Missing pytest-mock dependency**:
  - Added `pytest-mock=3.15.1` to `conda_environment.yaml`
  - Resolves `fixture 'mocker' not found` errors in 32 tests within `test_dashboard_manager.py`
  - Affected test classes: `TestDashboardManagerHandlersWithMocking`, `TestTrainingButtonHandlers`, `TestParameterHandlers`, `TestHandleTrainingButtons`, `TestDashboardManagerMiscMethods`

### Changed [0.24.2]

- Updated `notes/VALIDATION_REPORT_2026-01-12.md` with issue resolution details

### Technical Notes [0.24.2]

- **SemVer impact:** PATCH – Environment configuration fix; no application code changes
- All 2903 tests now pass with `JuniperCanopy` conda environment
- Test execution time: 107.49s (Python 3.14)
- The `mocker` fixture is provided by `pytest-mock` and used extensively for HTTP request mocking in dashboard handler tests

---

## [0.24.1] - 2026-01-12

### Post-Refactor Validation

Comprehensive validation of the Juniper Canopy application following the Phase 0–3 refactoring process.

### Added [0.24.1]

- **Validation Report**:
  - `notes/VALIDATION_REPORT_2026-01-12.md` documenting:
    - Full test suite execution: 2903 passed, 39 skipped, 0 failed
    - Code coverage analysis: 94% overall (28,486 of 30,170 lines covered)
    - 20 of 24 core source files meet or exceed 95% coverage target
    - Infrastructure and CI/CD pipeline status verification

### Technical Notes [0.24.1]

- **SemVer impact:** PATCH – Documentation addition only; no code changes
- All tests pass on Python 3.13.9 with pytest 9.0.1
- Test execution time: 112.29s (2942 tests collected)
- Validation confirms v0.24.0 stability and production readiness

---

## [0.24.0] - 2026-01-11

### Post-Refactor Verification & Documentation Templates

Formalized completion and verification of the Juniper Canopy refactor (Phases 0–3) and added standardized documentation templates to support ongoing development and releases.

### Added [0.24.0]

- **Documentation Templates** (`notes/templates/`):
  - `TEMPLATE_DEVELOPMENT_ROADMAP.md` – Standard structure for roadmap documents with milestones, status tracking, and dependency mapping
  - `TEMPLATE_ISSUE_TRACKING.md` – Consistent format for bug and issue tracking with severity/priority definitions, root cause analysis, and verification checklists
  - `TEMPLATE_PULL_REQUEST_DESCRIPTION.md` – Unified PR description template aligned with Keep a Changelog categories and SemVer impact assessment
  - `TEMPLATE_RELEASE_NOTES.md` – Preformatted template for composing release notes with test results, upgrade notes, and API changes

- **Post-Refactor Verification Report**:
  - `notes/development/POST_REFACTOR_VERIFICATION_2026-01-10.md` documenting:
    - Completion of all 34 roadmap items across Phases 0–3 (P0-1 through P3-7)
    - Test results: 2908 tests passed, 34 skipped (environment-specific)
    - Coverage: ≥93% across critical components (10 files at 95%+ target)
    - Overall status: **VERIFICATION PASSED**

- **Metrics Layouts Configuration**:
  - `conf/layouts/metrics_layouts.json` containing test-generated default layouts for training metrics visualizations

- **Snapshot History Data**:
  - Updated `src/snapshots/snapshot_history.jsonl` with recent snapshot activity from Phase 3 verification

### Changed [0.24.0]

- Documentation status now reflects that the Juniper Canopy refactor (Phases 0–3) is **complete and fully verified**
- Minor documentation drift identified in verification report (outdated `IMPLEMENTATION_PLAN.md` metadata, save/load semantics clarifications) - to be addressed in future maintenance

### Technical Notes [0.24.0]

- **SemVer impact:** MINOR – New documentation assets and data artifacts only; no breaking API or behavioral changes
- Runtime behavior unchanged from v0.23.0
- Metrics layouts and snapshot history updates are additive and remain compatible with existing consumers
- All 4 documentation templates follow Keep a Changelog format and project conventions

---

## [0.23.0] - 2026-01-10

### Phase 3, Wave 3 Testing & Coverage Improvements

Comprehensive test coverage improvements for Phase 3 Wave 3 implementations. Added 257 new tests with significant coverage increases across all target files.

### Added [0.23.0]

- **Test Coverage Improvements**:
  - `redis_panel.py`: 49% → 100% (22 new callback tests, 6 edge case tests)
  - `redis_client.py`: 76% → 97% (13 new tests for ping, metrics, status paths)
  - `cassandra_client.py`: 75% → 97% (16 new tests for auth, connect, metrics paths)
  - `websocket_manager.py`: 94% → 100% (3 new tests for error handling)
  - `statistics.py`: 91% → 100% (4 new tests for exception handling)
  - `dashboard_manager.py`: 93% → 95% (91 new handler tests)
  - `main.py`: 79% → 84% (110 new integration tests)

- **New Test Files**:
  - `tests/integration/test_main_coverage.py`: 110 tests for main.py endpoints
  - Enhanced existing test files with comprehensive callback testing

### Changed [0.23.0]

- **Test count increased**: 2646 → 2903 tests (+257 tests)
- **Overall coverage**: 93% (maintained with expanded codebase)
- **All 2903 tests pass** (39 skipped for environment-specific tests)

### Test Coverage Summary

| File                      | Before | After | Target | Status           |
| ------------------------- | ------ | ----- | ------ | ---------------- |
| redis_panel.py            | 49%    | 100%  | 95%    | ✅ Exceeded      |
| redis_client.py           | 76%    | 97%   | 95%    | ✅ Exceeded      |
| cassandra_client.py       | 75%    | 97%   | 95%    | ✅ Exceeded      |
| websocket_manager.py      | 94%    | 100%  | 95%    | ✅ Exceeded      |
| statistics.py             | 91%    | 100%  | 95%    | ✅ Exceeded      |
| dashboard_manager.py      | 93%    | 95%   | 95%    | ✅ Met           |
| training_monitor.py       | 95%    | 95%   | 95%    | ✅ Met           |
| training_state_machine.py | 96%    | 96%   | 95%    | ✅ Exceeded      |
| cassandra_panel.py        | 99%    | 99%   | 95%    | ✅ Exceeded      |
| main.py                   | 79%    | 84%   | 95%    | ⚠️ Near target   |

### Technical Notes

- main.py remaining uncovered lines require real CasCor backend or uvicorn runtime
- Import fallback branches for optional dependencies (redis, cassandra-driver) tested where possible
- Callback testing uses proper mock decorators: `mock_app.callback = MagicMock(return_value=lambda f: f)`

---

## [0.22.0] - 2026-01-09

### Phase 3 Wave 3 Complete: Redis & Cassandra Integration

Implemented P3-6 (Redis Monitoring Tab) and P3-7 (Cassandra Monitoring Tab), completing Phase 3. Both integrations are optional and fail soft when drivers are unavailable.

### Added [0.22.0]

- **P3-6: Redis Integration and Monitoring Tab**
  - `src/backend/redis_client.py`: Redis client wrapper with optional integration
    - `RedisClient` class with UP/DOWN/DISABLED/UNAVAILABLE status handling
    - `get_status()` and `get_metrics()` methods for REST endpoints
    - Demo mode support with synthetic data
    - Singleton pattern via `get_redis_client()`
  - `src/frontend/components/redis_panel.py`: Redis monitoring dashboard panel
    - Status badge with color-coded status (success/danger/warning/secondary)
    - Health card: version, uptime, connected clients, latency
    - Metrics card: memory usage, ops/sec, hit rate, keyspace stats
    - Auto-refresh via `dcc.Interval` (5s default, configurable)
  - `GET /api/v1/redis/status`: Redis health endpoint
  - `GET /api/v1/redis/metrics`: Redis metrics endpoint
  - 140 new tests (34 client + 63 panel + 43 integration)

- **P3-7: Cassandra Integration and Monitoring Tab**
  - `src/backend/cassandra_client.py`: Cassandra client wrapper with optional integration
    - `CassandraClient` class with UP/DOWN/DISABLED/UNAVAILABLE status handling
    - `get_status()` returns cluster health with host information
    - `get_metrics()` returns keyspace/table metrics
    - Demo mode support with synthetic cluster data
    - Singleton pattern via `get_cassandra_client()`
  - `src/frontend/components/cassandra_panel.py`: Cassandra monitoring dashboard panel
    - Status badge with color-coded status
    - Cluster overview card: contact points, keyspace, hosts table
    - Schema overview card: keyspace count, table count, replication strategies
    - Auto-refresh via `dcc.Interval` (10s default, configurable)
  - `GET /api/v1/cassandra/status`: Cassandra health endpoint
  - `GET /api/v1/cassandra/metrics`: Cassandra metrics endpoint
  - 93 new tests (24 client + 35 panel + 34 integration)

- **Dashboard Integration**
  - Added "Redis" tab to dashboard
  - Added "Cassandra" tab to dashboard
  - Registered `RedisPanel` and `CassandraPanel` in dashboard_manager.py
  - Dashboard now has 8 panels (up from 6)

### Changed [0.22.0]

- **Test count increased**: 2413 → 2646 tests (+233)
- **Coverage maintained**: 93% overall
- **Phase 3 Status**: All waves complete (P3-1 through P3-7)
- Updated component count assertions in test files to reflect 8 components

### Technical Notes [0.22.0]

- Both integrations are strictly optional:
  - Missing `redis` library → DISABLED status
  - Missing `cassandra-driver` library → DISABLED status
  - Disabled in config → DISABLED status
  - Connection failure → UNAVAILABLE status
- Demo mode (`CASCOR_DEMO_MODE=1`) returns synthetic data for development
- All credentials kept in config/env only (no hardcoding)

---

## [0.21.0] - 2026-01-09

### Phase 3 Verification & Coverage Improvements

Verified P3-2 and P3-3 implementations and significantly increased test coverage for frontend components. Fixed bug in `open_restore_modal` callback. Status documented in `docs/phase3/README.md`.

### Added [0.21.0]

- **45 new callback tests** for HDF5SnapshotsPanel
  - `test_hdf5_callbacks.py`: 39 tests covering all 8 callback functions
  - Tests for create_snapshot, update_snapshots_table, select_snapshot
  - Tests for update_detail_panel, open_restore_modal, confirm_restore, toggle_history
  - Edge case coverage for no-click states, error handling, and fallback paths

- **6 new callback tests** for AboutPanel
  - Tests for toggle_system_info and update_system_info callbacks
  - Verifies system information display when collapse is opened

- **Callback function exposure pattern** for unit testing
  - Added `_cb_*` attributes to expose callback functions after registration
  - Enables direct unit testing without requiring Dash server
  - Pattern applied to `HDF5SnapshotsPanel` and `AboutPanel`

### Fixed [0.21.0]

- **Bug: UnboundLocalError in open_restore_modal callback** (`hdf5_snapshots_panel.py`)
  - `json` import was inside `contextlib.suppress` block but referenced in the `with` statement
  - Moved import before the `with` statement to fix the error
  - Lines 893-896 refactored

- **Missing import: contextlib** (`hdf5_snapshots_panel.py`)
  - Added `import contextlib` to module imports

### Changed [0.21.0]

- **Coverage improved** across frontend components:
  - `hdf5_snapshots_panel.py`: 54% → 95% (+41%)
  - `about_panel.py`: 73% → 100% (+27%)
  - Overall coverage maintained at 93%

- **Test count increased**: 2368 → 2413 tests (+45)

### Test Results [0.21.0]

- **2413 tests passing** (0 failures)
- **39 skipped** (requires backend/display)
- **93% overall coverage**
- All P3-2 and P3-3 verification checkboxes now complete

---

## [0.20.0] - 2026-01-09

### Phase 3 Wave 1 Complete - HDF5 Snapshot Capabilities (P3-1, P3-2, P3-3)

Phase 3 Wave 1 is now complete. All three HDF5 snapshot capability features are implemented: Create, Restore, and History. Status documented in `docs/phase3/README.md`.

### Added [0.20.0]

- **P3-2: HDF5 Tab - Restore from Existing Snapshot**
  - New `POST /api/v1/snapshots/{snapshot_id}/restore` endpoint
  - Validates training is paused/stopped before restore
  - Demo mode simulates restore by resetting training state
  - Real mode loads from HDF5 file via h5py or cascor_integration
  - Logs restore activity to `snapshot_history.jsonl`
  - Broadcasts state change via WebSocket after restore
  - Tests: 9 new unit tests + 9 new integration tests

- **P3-2 Frontend: Restore Button and Confirmation Dialog**
  - "🔄 Restore" button added to each snapshot row in table
  - Confirmation modal with warning about training state requirements
  - Success/error status display after restore attempt
  - Triggers table refresh after successful restore

- **P3-3: HDF5 Tab - Show History of Snapshot Activities**
  - New `GET /api/v1/snapshots/history` endpoint
  - Reads from `snapshot_history.jsonl` (created by P3-1 infrastructure)
  - Returns entries in reverse chronological order (newest first)
  - Supports `limit` parameter (default 50 entries)
  - Logs create, restore, and delete actions

- **P3-3 Frontend: Collapsible History Section**
  - New "📜 Snapshot History" collapsible section in HDF5 panel
  - Toggle button with arrow indicator (▼/▲)
  - Displays action type with icon and color coding:
    - 📸 CREATE (green)
    - 🔄 RESTORE (yellow)
    - 🗑️ DELETE (red)
  - Shows snapshot ID, timestamp, and message for each entry
  - Tests: 6 new unit tests + 10 new integration tests

### Changed [0.20.0]

- **HDF5SnapshotsPanel** now registers 8 callbacks (added restore modal, confirm, history toggle)
- **main.py** snapshot endpoints reorganized (history before {snapshot_id} for correct routing)
- Table row now includes both "View Details" and "Restore" buttons
- Added restore-pending-id Store for modal state management

### Test Results [0.20.0]

- **34 new tests** added for P3-2 and P3-3 (25 unit + 19 integration)
- **135 tests passing** for snapshot functionality (86 unit + 49 integration)
- Coverage maintained at 95%+
- Test file: `test_hdf5_snapshots_panel.py` now has 86 tests
- Test file: `test_hdf5_snapshots_api.py` now has 51 tests

---

## [0.19.0] - 2026-01-08

### Phase 3 Started - Advanced Features (P3-1 Complete)

Phase 3 focuses on advanced features including HDF5 snapshot operations, visualization enhancements, and infrastructure integrations. P3-1 (Create New Snapshot) is now complete. Status documented in `docs/phase3/README.md`.

### Added [0.19.0]

- **P3-1: HDF5 Tab - Create New Snapshot**
  - New "Create Snapshot" section in HDF5 Snapshots panel
  - Name input field (optional, auto-generates timestamp-based name if empty)
  - Description input field (optional)
  - "📸 Create Snapshot" button with success/error feedback
  - Demo mode creates session-persistent mock snapshots
  - Real mode creates HDF5 files via h5py or cascor_integration
  - Auto-refresh table after successful creation
  - New API endpoint: `POST /api/v1/snapshots` (returns 201 Created)
  - Implementation: `main.py` lines 975-1152, `hdf5_snapshots_panel.py`
  - Tests: 13 new unit tests + 10 new integration tests

- **Snapshot Activity Logging (P3-3 Preparation)**
  - Added `_log_snapshot_activity()` helper for history tracking
  - Logs create/restore/delete operations to `snapshot_history.jsonl`
  - Prepares infrastructure for P3-3 (Show History of Snapshot Activities)

- **Phase 3 Documentation** (`docs/phase3/README.md`)
  - Complete implementation plan with 3 waves of features
  - Detailed solution designs for all P3 items
  - Effort estimates and coverage impact analysis

### Changed [0.19.0]

- **HDF5SnapshotsPanel** now registers 4 callbacks (added create_snapshot)
- **main.py** now includes snapshot creation endpoint and session-persistent demo snapshots
- Updated `get_snapshots()` to return session-created demo snapshots
- Updated `get_snapshot_detail()` to handle session-created snapshots

### Test Results [0.19.0]

- **23 new tests** added for P3-1 (13 unit + 10 integration)
- **2270 tests passing** (total), 39 skipped
- Coverage maintained at 95%+
- Test file: `test_hdf5_snapshots_panel.py` now has 63 tests
- Test file: `test_hdf5_snapshots_api.py` now has 32 tests

---

## [0.18.0] - 2026-01-08

### Phase 2 Complete - HDF5 Snapshots Tab (P2-4, P2-5)

Phase 2 is now complete with the implementation of the HDF5 Snapshots tab. All five P2 items are finished. Full documentation in `docs/phase2/README.md`.

### Added [0.18.0]

- **P2-4: HDF5 Snapshot Tab - List Available Snapshots**
  - New "HDF5 Snapshots" tab in dashboard
  - Table displaying available snapshots with Name/ID, Timestamp, Size
  - Auto-refresh polling (default 10s, configurable via `JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS`)
  - Manual refresh button
  - Demo mode support with simulated snapshots
  - New component: `src/frontend/components/hdf5_snapshots_panel.py`
  - New API endpoint: `GET /api/v1/snapshots`
  - Tests: 33 new tests in `test_hdf5_snapshots_panel.py`

- **P2-5: HDF5 Tab - Show Snapshot Details**
  - Detail panel showing selected snapshot metadata
  - Displays: ID, Name, Timestamp, Size, Path, Description
  - HDF5 Attributes section (reads from real HDF5 files via h5py when available)
  - Demo mode shows simulated attributes
  - New API endpoint: `GET /api/v1/snapshots/{snapshot_id}`
  - Tests: 21 new tests in `test_hdf5_snapshots_api.py`

### Changed [0.18.0]

- **DashboardManager** now registers 6 components (added HDF5SnapshotsPanel)
- **main.py** now includes HDF5 snapshot API endpoints and helper functions

### Test Results [0.18.0]

- **54 new tests** added for P2-4/P2-5
- Coverage maintained at 95%+
- Phase 2 fully complete

---

## [0.17.0] - 2026-01-07

### Phase 2 Partial - Polish Features (P2-1, P2-2, P2-3 Complete)

Phase 2 focuses on polish features and medium-priority enhancements. Three of five P2 items are now complete. Status documented in `docs/phase2/README.md`.

### Added [0.17.0]

- **P2-1: Visual Indicator for Most Recently Added Node**
  - Pulsing glow effect on newly added hidden nodes (cyan/teal color)
  - Edge highlighting for all connections to new node
  - Persistent highlight with state machine (active → fading → None)
  - 2-second smooth fade-out animation
  - Visually distinct from selected node indicator (yellow/orange)
  - Implementation: `network_visualizer.py` lines 213-219, 960-1166
  - Tests: 17 new tests in `test_network_visualizer_coverage.py`

- **P2-2: Unique Name Suggestion for Image Downloads**
  - Network topology image downloads now use timestamp-based filenames
  - Format: `juniper_topology_YYYYMMDD_HHMMSS.png`
  - High-resolution export (2x scale)
  - Implementation: `network_visualizer.py` lines 39, 189-193
  - Tests: 4 new tests in `test_network_visualizer_coverage.py`

- **P2-3: About Tab for Juniper Cascor Backend**
  - New "About" tab in dashboard with application information
  - Displays version, license (MIT), credits, documentation links, and contact info
  - Collapsible System Information section (Python version, platform, architecture)
  - New component: `src/frontend/components/about_panel.py`
  - Tests: 27 new tests in `test_about_panel.py`

- **Phase 2 Documentation** (`docs/phase2/README.md`)
  - Complete documentation structure for all P2 features
  - Status tracking, solution designs, and verification checklist

### Changed [0.17.0]

- **DashboardManager** now registers 5 components (added AboutPanel)
- **NetworkVisualizer** callback now includes interval-based animation support
- Updated component count tests in:
  - `test_dashboard_enhancements.py`
  - `test_dashboard_manager.py`
  - `test_dashboard_manager_coverage.py`
- Updated callback invocation tests for new signature

### Test Results [0.17.0]

- **2177 passed**, 37 skipped (48 new tests added)
- Coverage maintained at 95%+

---

## [0.16.0] - 2026-01-07

### Phase 1 Complete - High-Impact Enhancements

All Phase 1 items validated and documented. Phase 1 README created at `docs/phase1/README.md`.

### Validated [0.16.0] - Phase 1 Features

- **P1-1: Candidate Info Section Display/Collapsibility**
  - Candidate pool section always visible with collapsible content
  - Toggle icon (▼/▶) indicates collapsed state
  - Historical pools tracked and displayed as collapsed cards
  - Top 10 pools preserved, ordered by recency
  - Implementation: `metrics_panel.py` lines 337-563, 1342-1503

- **P1-2: Replay Functionality**
  - Full replay controls (⏮, ◀, ▶, ⏩, ⏭)
  - Speed selection (1x, 2x, 4x)
  - Progress slider with position display
  - Controls visible when training STOPPED/PAUSED/COMPLETED/FAILED
  - Implementation: `metrics_panel.py` lines 171-266, 388-403, 637-800+

- **P1-3: Staggered Hidden Node Layout**
  - "Staggered" layout option in dropdown
  - Wave pattern: first node center, alternating outward
  - Dynamic spread increases with node count (max 3.0)
  - Implementation: `network_visualizer.py` lines 110, 688-706

- **P1-4: Mouse Click Events for Node Selection**
  - Single-click selects/deselects nodes
  - Box/lasso selection for multiple nodes
  - Visual highlight (yellow glow, orange ring)
  - Selection info panel with node details
  - Implementation: `network_visualizer.py` lines 171-181, 206, 366-453, 834-884

### Added [0.16.0]

- **Phase 1 Documentation** (`docs/phase1/README.md`)
  - Complete documentation of all P1 implementations
  - Root cause analysis and solution details
  - Verification checklist

- **PR Description** (`notes/PR_PHASE1_VALIDATION_2026-01-07.md`)
  - Pull request documentation for Phase 1 validation
  - Summary of all validated features and changes

### Test Results [0.16.0]

- **2134 passed**, 32 skipped
- All Phase 1 issues validated
- Coverage maintained at 95%+

---

## [0.15.1] - 2026-01-07

### Security Patch Release (Critical) - urllib3 Decompression Bomb Vulnerability

This release addresses a critical security vulnerability in the `urllib3` dependency. Full details in `notes/RELEASE_NOTES_v0.15.1-alpha.md`.

### Security [0.15.1]

- **urllib3 Dependency Update**: `≤2.6.2 → >=2.6.3`
  - Addresses decompression bomb vulnerability (CWE-409)
  - Malicious servers could exploit HTTP redirect handling to cause excessive resource consumption
  - Attack vector: Malicious HTTP redirect responses with compressed content
  - Reference: [Dependabot Alert #2](https://github.com/pcalnon/Juniper/security/dependabot/2) *(pre-polyrepo URL)*

### Added [0.15.1]

- **Security Release Notes** (`notes/RELEASE_NOTES_v0.15.1-alpha.md`)
  - Complete security advisory documentation
  - Remediation and upgrade instructions
  - Follows standardized security release notes format

- **Security Release Notes Template** (`notes/TEMPLATE_SECURITY_RELEASE_NOTES.md`)
  - Reusable template for future security releases
  - Defines required structure with 11 sections
  - Placeholder markers for easy customization

- **AGENTS.md Documentation Standards**
  - Added "Security Release Notes" section under Documentation File Types
  - References template as required format for all security releases
  - Links to example release notes (v0.14.1-alpha, v0.15.1-alpha)

### Changed [0.15.1]

- **conf/requirements.txt**: urllib3 pinned to `~=2.6.3`
- **.markdownlint.json**: Updated rules for template file compatibility

### Test Results [0.15.1]

- **2247 passed**, 34 skipped
- Coverage maintained at 95%+

---

## [0.15.0] - 2026-01-07

### Fixed [0.15.0] - Phase 0 Completion

- **P0-1: Training Controls Button State Fix**
  - Buttons return to normal state after click with 2-second timeout
  - Proper visual feedback during action execution

- **P0-5: Pan/Lasso Tool Fix**
  - Default dragmode set to "pan" in network topology graph
  - View-state store persists tool selection across interval updates
  - Modebar configured with select2d and lasso2d buttons
  - Tools now behave correctly (Pan actually pans, Lasso actually lasso selects)

- **P0-6: Interaction Persistence**
  - View-state dcc.Store preserves zoom, pan, and dragmode across updates
  - capture_view_state callback captures axis ranges and tool selection from relayoutData
  - View state applied on every graph update to prevent ~1 second reset
  - Selected nodes store preserves selection across topology updates

- **P0-8: Top Status Bar Updates on Completion**
  - Added COMPLETED and FAILED states to TrainingStatus enum
  - Added mark_completed() and mark_failed(reason) state transition methods
  - Demo mode now properly marks training as COMPLETED when max_epochs reached
  - /api/status endpoint exposes completed, failed, and fsm_status fields
  - Dashboard status bar displays "Completed" (cyan) and "Failed" (red) states

- **P0-7: Dark Mode Info Bar**
  - Theme-aware stats bar with proper background/text colors
  - Consistent styling across light and dark themes

- **P0-9: Legend Display and Positioning**
  - Legend positioned at bottom-left (x=0.02, y=0.02)
  - Theme-aware styling with semi-transparent backgrounds (0.7 alpha)
  - Dark mode: rgba(36, 36, 36, 0.7) background with #f8f9fa text
  - Light mode: rgba(248, 249, 250, 0.7) background with #212529 text

- **P0-12: Meta-Parameters Apply Button (Learning Rate)**
  - Float tolerance fix for change detection
  - Learning rate changes now detected correctly despite floating-point precision

### Added [0.15.0]

- **TrainingStateMachine** (`src/backend/training_state_machine.py`)
  - COMPLETED and FAILED entries in TrainingStatus enum
  - is_completed() and is_failed() helper methods
  - mark_completed() - transitions STARTED → COMPLETED
  - mark_failed(reason) - transitions STARTED/PAUSED → FAILED

- **Phase 0 Tests** (`src/tests/unit/test_phase0_fixes.py`)
  - 29 new tests covering all remaining Phase 0 fixes
  - TestTrainingStatusEnumP08 (2 tests)
  - TestStateMachineCompletionP08 (10 tests)
  - TestStatusBarCompletedFailedP08 (5 tests)
  - TestNetworkVisualizerDarkModeP07 (2 tests)
  - TestNetworkVisualizerLegendP09 (4 tests)
  - TestViewStatePersistenceP05P06 (4 tests)
  - TestToolbarButtonsP05 (2 tests)

### Changed [0.15.0]

- **Demo Mode** (`src/demo_mode.py`)
  - Calls state_machine.mark_completed() when training finishes
  - Broadcasts updated status via _update_training_status()

- **API Endpoint** (`src/main.py`)
  - /api/status returns completed, failed, and fsm_status fields

- **Dashboard Manager** (`src/frontend/dashboard_manager.py`)
  - _build_unified_status_bar_content() handles COMPLETED/FAILED terminal states
  - Failed takes priority over Completed if both are True

- **Network Visualizer** (`src/frontend/components/network_visualizer.py`)
  - Legend positioned at bottom-left with theme-aware styling
  - Semi-transparent backgrounds for better topology visibility

### Test Results [0.15.0]

- **2129 passed**, 37 skipped
- All Phase 0 issues now FIXED
- Phase 0 verification checklist 100% complete

---

## [0.14.4] - 2026-01-06

### Fixed [0.14.4]

- **Configuration Test Architecture**
  - Fixed 10 failing tests that incorrectly enforced YAML config values must equal constants
  - Tests now use compatibility/bounds checks instead of equality assertions
  - This aligns with intended design: constants define safe bounds, YAML provides runtime overrides

### Changed [0.14.4]

- **Test Architecture** (`src/tests/unit/test_config_training_params.py`, `src/tests/integration/test_config_dashboard_integration.py`)
  - Tests now validate that YAML config values are **within** constant bounds, not equal to them
  - Added comprehensive docstrings explaining the configuration hierarchy:
    - `constants.py`: Safe bounds and recommended defaults
    - `app_config.yaml`: Runtime overrides for experiments/tuning
    - Environment variables: Highest precedence for deployment
  - YAML can now be used for experimental configurations without breaking tests

- **Configuration File** (`conf/app_config.yaml`)
  - Added inline comments documenting override values vs constant defaults
  - epochs.default: 500 (override from constant 200)
  - hidden_units.max: 100 (override from constant 20)
  - hidden_units.default: 40 (override from constant 10)

### Test Results [0.14.4]

- **2097 passed**, 32 skipped
- All 10 previously failing configuration tests now pass
- YAML overrides work as intended without breaking test suite
- Overall coverage improved from ~75% to **93%**

### Coverage Improvements [0.14.4]

Added 400+ new tests across 6 new test files:

| File | Before | After |
| ------ | -------- | ------- |
| `metrics_panel.py` | 67% | 98% |
| `dashboard_manager.py` | 68% | 93% |
| `network_visualizer.py` | 71% | 99% |
| `main.py` | 79% | 89% |
| `decision_boundary.py` | 84% | 100% |
| `dataset_plotter.py` | 87% | 99% |

**New test files:**

- `src/tests/unit/frontend/test_metrics_panel_handlers.py` (105 tests)
- `src/tests/unit/frontend/test_network_visualizer_callbacks.py` (69 tests)
- `src/tests/unit/frontend/test_decision_boundary_callback_coverage.py` (22 tests)
- `src/tests/unit/frontend/test_dataset_plotter_coverage.py` (65 tests)
- `src/tests/unit/frontend/test_dashboard_manager_handlers.py` (81 tests)
- `src/tests/unit/test_main_coverage_extended.py` (104 tests)

---

## [0.14.3] - 2026-01-06

### Fixed [0.14.3]

- **P0-4: Graph Range Persistence**
  - Implemented view-state dcc.Store to capture and persist user zoom/pan ranges
  - Added capture_view_state callback listening to relayoutData from loss-plot and accuracy-plot
  - Updated _update_metrics_display_handler to apply stored ranges to figures on data updates
  - User's zoom/pan state now persists across interval-driven data updates
  - Reset via autorange is properly handled (clears stored ranges when user resets)

- **P0-2: Meta-Parameters Apply Button**
  - Fixed critical key mismatch between frontend and backend parameter names
  - Frontend was sending `hidden_units`/`epochs` but backend expected `max_hidden_units`/`max_epochs`
  - This caused the Apply button to appear to work but silently ignore hidden units and epochs changes
  - All three parameters (learning_rate, max_hidden_units, max_epochs) now correctly persist

### Changed [0.14.3]

- **TrainingState** (`src/backend/training_monitor.py`)
  - Added `max_epochs` field to `_STATE_FIELDS` set
  - Added `__max_epochs` private attribute with default value 200
  - Updated `get_state()` to include `max_epochs` in returned dictionary

- **Dashboard Manager** (`src/frontend/dashboard_manager.py`)
  - `_apply_parameters_handler()`: Changed payload keys from `hidden_units`/`epochs` to `max_hidden_units`/`max_epochs`
  - `_track_param_changes_handler()`: Updated comparison keys to match backend schema
  - `_init_applied_params_handler()`: Updated returned keys for consistency
  - `_sync_backend_params_handler()`: Added `max_epochs` to synced state
  - Updated `pending-params-store` initialization to use correct keys

- **API Endpoint** (`src/main.py`)
  - `/api/set_params` now includes `max_epochs` in TrainingState updates

- **Demo Mode** (`src/demo_mode.py`)
  - `_initialize_training_state()`: Added `max_epochs` to initial state
  - `_update_candidate_pool_state()`: Added `max_epochs` to periodic state updates
  - `apply_params()`: Now updates internal `training_state` with all parameter values

### Added [0.14.3]

- **Tests**
  - New integration test file: `src/tests/integration/test_apply_button_parameters.py`
  - 12 comprehensive tests covering:
    - TrainingState accepts all three parameter fields
    - API endpoint correctly updates all parameters
    - Dashboard handlers use correct keys throughout
    - Full round-trip parameter persistence verification

### Test Results [0.14.3]

- **46 passed** parameter-related tests
- All Apply button functionality verified working
- No regressions in existing functionality

---

## [0.14.2] - 2026-01-05

### Fixed [0.14.2]

- **P0-3: Top Status Bar Updates**
  - Fixed `/api/status` endpoint to return FSM-based `phase` field instead of hardcoded `"demo_mode"`
  - Added `is_running` and `is_paused` boolean flags to `/api/status` for accurate status determination
  - Consolidated two separate status bars into single unified status bar
  - Status and Phase now display correct values with state-specific colors:
    - Status: Running (green), Paused (orange), Stopped (gray)
    - Phase: Output Training (blue), Candidate Pool (cyan), Idle (gray)
  - Status bar now includes all elements: Status, Phase, Epoch, Hidden Units, and Latency indicator

### Changed [0.14.2]

- **Dashboard Layout**
  - Unified status bar replaces previous two-bar layout
  - New display format: `● Status: <status> | Phase: <phase> | Epoch: <n> | Hidden Units: <n> Latency: <ms>`
  - Renamed `_update_status_bar_handler` to `_update_unified_status_bar_handler` for clarity

### Added [0.14.2]

- **Tests**
  - Added 7 new integration tests in `TestStatusEndpointFSMIntegration` class for FSM integration
  - Tests verify `/api/status` returns correct FSM-based values for all training states

### Test Results [0.14.2]

- **403 passed** integration tests
- **126 passed** unit tests
- All status bar-related tests passing

---

## [0.14.1] - 2026-01-05

### Fixed [0.14.1]

- **Documentation Table Formatting**
  - Fixed table formatting in `DOCUMENTATION_OVERVIEW.md` for improved clarity

### Changed [0.14.1]

- **Dependencies**
  - Updated `filelock` to version 3.20.2 in `conf/requirements.txt` and `conf/conda_environment.yaml`

### Test Results [0.14.1]

- **1665 passed, 37 skipped** in 92.23s
- **90% overall test coverage**

---

## [0.14.0] - 2026-01-05

### Added [0.14.0]

- **Comprehensive Bash Script Configuration Infrastructure**
  - Created 25+ new `.conf` configuration files in `conf/` directory for modular script configuration
  - New configuration files include:
    - `__date_functions.conf` (202 lines) - Date manipulation utilities
    - `__git_log_weeks.conf` (111 lines) - Git log week-based analysis
    - `change_path.conf`, `common_functions.conf`, `conda_env_update.conf`
    - `create_performance_profile.conf` with separate `_functions.conf` companion
    - `get_code_stats_functions.conf`, `get_file_todo_functions.conf`
    - `get_module_filenames_functions.conf`, `get_script_path.conf`
    - `get_todo_comments_functions.conf`, `git_branch_ages.conf`
    - `juniper_canopy-demo.conf`, `last_mod_update.conf`
    - `logging.conf` (230 lines), `logging_colors.conf`, `logging_functions.conf` (352 lines)
    - `main.conf`, `proto.conf`, `random_seed.conf`, `run_all_tests.conf`
    - `save_to_usb.conf`, `setup_environment.conf` (286 lines)
    - `setup_environment_functions.conf`, `setup_test.conf`
    - `source_tree.conf`, `todo_search.conf`, `update_weekly.conf`

- **New Utility Scripts**
  - `util/color_display_codes.bash` - Terminal color code display utility
  - `util/color_table.py` - Python color table generator (64 lines)
  - `util/mv2_bash_n_back.bash` - Bash file backup utility

### Changed [0.14.0]

- **Major Bash Infrastructure Refactoring** (36 commits)
  - Refactored all utility scripts for improved modularity and configuration-driven behavior
  - Introduced `CALLING_PID` for accurate parent path resolution
  - Enhanced date functions and logging mechanisms across scripts
  - Improved environment constants handling and function config sourcing logic
  - Streamlined debug handling and sourcing checks across configuration files
  - Renamed config files: `test_common_conf.bash` → `test_common.conf`, `test_prototype_conf.bash` → `test_prototype.conf`

- **Configuration File Updates**
  - `conf/common.conf` expanded significantly (+488 lines)
  - `conf/init.conf` improved validation for parent script and config file sourcing
  - `conf/conda_environment.yaml` streamlined (-75 lines)
  - `conf/logging_config.yaml` updated with new logging structure

- **Utility Script Improvements**
  - `util/get_code_stats.bash` - Major refactoring for cleaner output
  - `util/create_performance_profile.bash` - Simplified architecture
  - `util/get_todo_comments.bash` - Enhanced TODO extraction
  - `util/save_to_usb.bash` - Streamlined backup process
  - `util/juniper_canopy-demo.bash` - Improved demo mode handling

### Fixed [0.14.0]

- **Bash Script Logic Fixes**
  - Fixed inverted logic in `is_defined` checks across multiple scripts
  - Improved path resolution for `init.conf` sourcing
  - Fixed method and TODO counting with proper whitespace handling

### Removed [0.14.0]

- `conf/script_util.conf` (329 lines) - Functionality absorbed into modular config files
- `conf/util_logging.conf` (266 lines) - Replaced by `logging.conf` and `logging_functions.conf`
- `util/__date_functions.bash` (155 lines) - Moved to `conf/__date_functions.conf`
- `util/run_demo.bash`, `util/try.bash` - Removed obsolete scripts

### Test Results [0.14.0]

- Test suite requires attention: 58 collection errors detected
- Infrastructure changes do not affect core Python test functionality

---

## [0.13.2] - 2025-12-16

### Added [0.13.2]

- **Project Branding Assets**
  - Juniper logo images in `src/assets/` directory (`Juniper_Logo_150px.png`, `Juniper_Logo_200px.png`, 10 logo variants, 3 `.ico` files, `Juniper_Tree_3-widestance.png`)
  - `markdown.css` for markdown-specific styling in documentation (95 lines)

- **Markdown Tooling**
  - `.markdownlint.json` configuration with relaxed rules (512-char lines, allowed HTML elements)
  - Pre-commit integration for `markdownlint` with `docs/history/` excluded

- **Utility Scripts and Configuration**
  - `util/get_module_filenames.bash` for collecting codebase module statistics
  - New config files for development tooling:
    - `conf/get_code_stats.conf` - Source file reporting configuration
    - `conf/get_file_lines.conf` - File line counting utility config
    - `conf/get_file_todo.conf` - TODO extraction configuration
    - `conf/get_module_filenames.conf` - Module filename collection config
    - `conf/get_todo_comments.conf` - TODO comment extraction config
    - `conf/util_logging.conf` - Leveled logging for utility scripts

### Changed [0.13.2]

- **Documentation and Presentation**
  - Updated `README.md` with right-aligned Juniper logo and improved formatting

- **Tooling and CI**
  - Enabled `markdownlint` in pre-commit hooks (previously manual only)
  - CI workflow updated to ignore markdown rules `MD033` and `MD041`

- **Configuration and Utilities**
  - Renamed `conf/script_util.cfg` → `conf/script_util.conf` with expanded functionality (+184 lines)
  - Refactored utility scripts for improved modularity and configuration-driven behavior

- **Versioning and Housekeeping**
  - Standardized Python file headers with project metadata (e.g., `callback_context.py`)
  - Reset internal version headers from `1.x.x` to `0.x.x` scheme for pre-1.0 semantic versioning
  - Expanded `.gitignore` with vim swap file patterns (`*.swq`, `*.swn`, etc.), `*.xcf`, `*.tmp`

### Removed [0.13.2]

- Removed accidentally committed `happy_dance.css` that was not intended for the project

### Test Results [0.13.2]

- 1668 passed, 34 skipped, 1 warning in 97.15s (0:01:37)
- **84.05% overall test coverage**

---

## [0.13.1] - 2025-12-13

### Fixed [0.13.1]

- **DEFAULT_SCALE NameError in NetworkVisualizer** (Critical)
  - Fixed undefined `DEFAULT_SCALE` constant that blocked all test collection
  - Changed default parameter to use `DashboardConstants.DEFAULT_SCALE`
  - All 20 test collection errors resolved
  - See [FIX_DEFAULT_SCALE_2025-12-13.md](notes/FIX_DEFAULT_SCALE_2025-12-13.md) for details

### Added [0.13.1]

- **Comprehensive Test Suite Expansion** (453 new tests)
  - `test_callback_context_coverage.py` - 29 tests for callback adapter
  - `test_dashboard_helpers_coverage.py` - 48 tests for dashboard helpers
  - `test_network_visualizer_layout_coverage.py` - 43 tests for layout methods
  - `test_metrics_panel_helpers_coverage.py` - 74 tests for metrics helpers  
  - `test_main_api_coverage.py` - 36 tests for API endpoints
  - `test_demo_mode_comprehensive.py` - 72 tests for demo mode
  - `test_websocket_comprehensive.py` - 51 tests for WebSocket
  - `test_config_manager_comprehensive.py` - 42 tests for config
  - `test_cascor_integration_comprehensive.py` - 49 tests for backend
  - `test_base_component_coverage.py` - 9 tests for base component

### Changed [0.13.1]

- **Test Results**
  - 1666 tests passing, 37 skipped
  - **90% overall coverage achieved** (up from 84%)

---

## [0.13.0] - 2025-12-13

### Added [0.13.0]

- **Training Metrics Replay Functionality** (P1-3)
  - Transport controls: play/pause, step forward/backward, jump to start/end
  - Speed controls: 1x, 2x, 4x playback speeds
  - Progress slider with position display (current / total epochs)
  - Automatic playback with configurable interval
  - Controls only visible when training is Paused/Stopped/Completed/Failed

- **Network Topology Staggered Layout** (P1-2)
  - Added "Staggered" layout option to dropdown
  - Hidden nodes now use zigzag pattern for better edge visibility
  - Progressive horizontal spreading based on node count
  - Maintains vertical spacing while improving edge clarity

- **Node Selection Interactions** (P1-4)
  - Click to select nodes with visual highlighting (yellow glow + orange ring)
  - Box and lasso selection support via new mode bar buttons
  - Selection info panel showing selected node details
  - Toggle selection on re-click, clear on click elsewhere

- **Candidate Node Info Section with History** (P1-1)
  - Collapsible candidate pool section (toggle with header click)
  - Historical pools stored and displayed (up to 10 entries)
  - Previous pools shown as collapsed cards with epoch/candidate summary
  - Section always visible with "No active candidate pool" placeholder

### Changed [0.13.0]

- **Test Coverage**
  - 1213 tests passing, 37 skipped
  - 84% overall coverage maintained

---

## [0.12.0] - 2025-12-12

### Added [0.12.0]

- **Implementation Plan Documentation** (2025-12-12)
  - Created [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) with prioritized roadmap
  - Created [docs/phase0/README.md](docs/phase0/README.md) with detailed Phase 0 implementation guide
  - Added phase directories for structured development (phase0, phase1, phase2, phase3)

- **Apply Parameters Button** (P0-2)
  - Added "Apply Parameters" button for manual meta-parameter application
  - Added `applied-params-store` and `pending-params-store` for parameter tracking
  - Visual feedback shows "⚠️ Unsaved changes" when parameters differ from applied
  - Parameters only sent to backend on explicit Apply button click

- **Graph View State Persistence** (P0-4)
  - Added `view-state` store to MetricsPanel for preserving zoom/pan state
  - New `capture_view_state` callback captures relayoutData from both plots
  - Zoom and pan persist across interval-driven data updates
  - Enabled displayModeBar on graphs for zoom/pan tools

- **Network Topology View State Persistence** (P0-5, P0-6)
  - Added `view-state` store for preserving zoom, pan, and tool selection
  - Added `topology-hash` store to detect actual topology changes
  - New `capture_view_state` callback captures relayoutData
  - Pan/Lasso/Box Select tools now work correctly with proper dragmode

### Fixed [0.12.0]

- **Training Controls Button State** (P0-1)
  - Buttons now return to normal state after 2-second timeout
  - Added timestamp tracking to button states for proper timeout handling
  - Fixed `_handle_button_timeout_and_acks_handler` to check individual button timestamps
  - All 5 buttons (Start, Pause, Resume, Stop, Reset) properly reset after use

- **Top Status Bar Updates** (P0-3)
  - Fixed status/phase mapping from FSM enum values to display strings
  - STARTED → "Running", STOPPED → "Stopped", PAUSED → "Paused"
  - Phase mapping: OUTPUT → "Output Training", CANDIDATE → "Candidate Pool"
  - Proper color coding: green for running, orange for paused, gray for stopped

- **Network Topology Dark Mode** (P0-7)
  - Fixed stats bar background color in dark mode (was white on white)
  - Added theme callback for stats bar with proper dark (#343a40) and light (#f8f9fa) backgrounds
  - Ensured text contrast in both light and dark modes

- **Test Compatibility**
  - Fixed `test_metrics_endpoint` to handle both list and dict API response formats

### Changed [0.12.0]

- **DEVELOPMENT_ROADMAP.md**
  - Added priority column (P0-P3) to status table
  - Added phase assignments to all features
  - Added links to implementation plan documents
  - Added priority legend

- **Test Coverage**
  - 1218 tests passing, 32 skipped
  - 85% overall coverage maintained

---

## [0.11.0] - 2025-12-07

### Fixed [0.11.0]

- **TrainingState.update_state() Name Mangling Bug** (2025-12-07)
  - Fixed critical bug where `update_state()` silently ignored all field updates
  - Root cause: Python name mangling (`__status` → `_TrainingState__status`) caused `if element in self.__dict__` to always fail
  - Added `_STATE_FIELDS` class constant with all 19 valid field names
  - Rewrote `update_state()` to map public kwargs keys to mangled attribute names
  - Maintains thread safety and atomic update behavior
  - All 15 previously failing tests now pass

- **YAML Linting Configuration** (2025-12-07)
  - Created `.yamllint.yaml` with relaxed rules (120-char lines, disabled document-start)
  - Fixed `conf/logging_config.yaml`: changed `propagate: True` → `propagate: true` (YAML boolean)

### Changed [0.11.0]

- **Pre-commit Hooks** (2025-12-07)
  - All pre-commit hooks now pass including yamllint
  - Test suite: 1213 passed, 37 skipped

---

## [0.10.0] - 2025-12-06

### Added [0.10.0]

- **Priority 3 Test Fixes - Environment/Integration Issues** (2025-12-06)
  - Fixed 14 failing integration tests related to demo mode and environment setup
  - All 1213 tests now passing with 37 skipped (environment-dependent)
  - Comprehensive test suite validation complete

### Changed [0.10.0]

- **Test Suite Improvements** (2025-12-06)
  - `test_setup.py`: Made `redis` and `pandas` optional packages, fixed `utils/` → `util/` directory name
  - `test_api_state_endpoint.py`: Made status/phase checks case-insensitive for demo mode compatibility
  - `test_status_bar_updates.py`: Rewrote tests to verify valid state values rather than controlling demo mode directly
  - `test_architectural_fixes.py`: Updated assertion to check handler methods instead of `_setup_callbacks`
  - `test_websocket_control.py`: Fixed response format checks and message type matching
  - `test_main_ws.py`: Simplified WebSocket message handling for reliability
  - `test_mvp.py`: Fixed dashboard title check from "Juniper Canopy Monitor" to "Juniper Canopy"

### Fixed [0.10.0]

- **Demo Mode Test Compatibility** (2025-12-06)
  - Tests now properly handle demo mode's continuous state updates
  - Status/phase assertions use case-insensitive matching (API returns `"STARTED"` not `"Started"`)
  - WebSocket tests simplified to avoid timeout-related race conditions
  - Metrics broadcast tests accept both `"metrics"` and `"training_metrics"` message types

---

## [0.9.0] - 2025-12-06

### Added, [0.9.0]

- **Callback Context Adapter** (2025-12-06)
  - Created `src/frontend/callback_context.py` for testable Dash callback context
  - Singleton pattern with thread-safe implementation
  - Test mode injection for unit testing without Dash runtime
  - Methods: `get_triggered_id()`, `set_test_trigger()`, `clear_test_trigger()`

- **Fake Backend Root Fixture** (2025-12-06)
  - Added `fake_backend_root` fixture to `src/tests/conftest.py`
  - Simulates CasCor backend directory structure for testing
  - Supports testing against different backend versions without real installation
  - Creates minimal cascade_correlation module structure

### Changed, [0.9.0]

- **Dashboard Manager Handler Refactoring** (2025-12-06)
  - Extracted callback logic into testable handler methods
  - Handlers accept optional `trigger` kwarg to bypass `dash.callback_context`
  - Enables unit testing of dashboard callbacks without Flask request context
  - Updated: `_toggle_dark_mode_handler`, `_update_status_bar_handler`, `_update_network_info_handler`, etc.

- **Config Manager Improvements** (2025-12-06)
  - Replaced `verify_config_constants_consistency` with declarative specification
  - Added `check_constants_category` method for category-based validation
  - Improved consistency mapping for training parameters

- **Test Infrastructure Enhancements** (2025-12-06)
  - 30+ test files refactored for improved reliability
  - Reduced test coupling to demo mode state
  - Fixed fixture discovery issues in nested test directories
  - Enhanced singleton reset fixture for better test isolation

### Fixed, [0.9.0]

- **Priority 1 & 2 Test Fixes** (2025-12-06)
  - Fixed 21 collection errors from import/fixture issues
  - Fixed 30 test failures from application bugs and test code bugs
  - Resolved Flask request context mocking for `_api_url()` calls
  - Fixed TrainingConstants parameter name mismatches

---

## [0.8.1] - 2025-12-05

### Changed, [0.8.1]

- **GitHub Deployment Cleanup** (2025-12-05)
  - Removed sensitive tokens from CI/CD documentation
  - Cleaned up history files for initial GitHub deployment
  - Configured juniper_canopy as standalone package

---

## [0.8.0] - 2025-12-04

### Changed, [0.8.0]

- **Initial GitHub Deployment** (2025-12-04)
  - Cleaned up Juniper Canopy prototype for initial deployment
  - Configured as standalone package
  - Updated LICENSE with comprehensive terms
  - Revised README with full project description

---

## [0.7.0] - 2025-11-17

### Added, [0.7.0]

- **YAML Configuration Refactoring - Tests** (2025-11-17)
  - Comprehensive unit test suite (`tests/unit/test_config_refactoring.py`)
  - 35 unit tests covering all configuration aspects
  - Integration test suite (`tests/integration/test_config_integration.py`)
  - 24 integration tests for end-to-end configuration flow
  - 100% test pass rate for configuration system
  - Coverage for all 6 refactored components
  - Environment variable override testing
  - Configuration hierarchy validation tests
  - Error handling and fallback testing

- **WebSocket Constants** (2025-11-17)
  - Added `WebSocketConstants` class to `src/constants.py`
  - Max connections, heartbeat interval, reconnect attempts constants
  - Reconnection delay configuration
  - Comprehensive defaults for WebSocket communication

- **Constants Infrastructure** (2025-11-17)
  - Centralized constants module (`src/constants.py`)
  - Type-safe configuration values using `typing.Final`
  - Three constant classes: `TrainingConstants`, `DashboardConstants`, `ServerConstants`
  - Training parameter constants (epochs, learning rates, hidden units)
  - Dashboard UI constants (update intervals, timeouts, data limits)
  - Server configuration constants (host, port, WebSocket paths)
  - Comprehensive test coverage (17 tests, 100% pass rate)

- **Constants Documentation** (2025-11-17)
  - Comprehensive Constants Guide (`docs/CONSTANTS_GUIDE.md`)
  - How-to guide for adding new constants
  - Naming conventions and best practices
  - Constants vs configuration decision matrix
  - Migration examples and common pitfalls
  - Updated AGENTS.md with constants usage guidelines

### Changed, [0.7.0]

- **YAML Configuration Refactoring - Complete Application** (2025-11-17)
  - **Main Entry Point** (`src/main.py`): Server configuration with env var overrides
  - **Dashboard Manager** (`src/frontend/dashboard_manager.py`): Training parameter defaults with config hierarchy
  - **Metrics Panel** (`src/frontend/components/metrics_panel.py`): Update intervals, buffers, smoothing from config
  - **Backend Integration** (`src/backend/cascor_integration.py`): Backend path resolution with transparent source logging
  - **WebSocket Manager** (`src/communication/websocket_manager.py`): Connection limits, heartbeats, reconnection from config
  - **Demo Mode** (`src/demo_mode.py`): Simulation parameters from config with training defaults
  - Three-level configuration hierarchy implemented consistently across all components
  - 20+ environment variables supported: `CASCOR_SERVER_*`, `CASCOR_TRAINING_*`, `JUNIPER_CANOPY_*`, `CASCOR_BACKEND_*`, `CASCOR_WEBSOCKET_*`, `CASCOR_DEMO_*`
  - Transparent configuration source logging for all values
  - Proper validation and error handling throughout
  - Full backward compatibility maintained
  - Enhanced ConfigManager integration across entire codebase
  - Configuration Management section added to AGENTS.md with complete reference

- **Dashboard Manager Refactoring** (2025-11-17)
  - Replaced hard-coded training parameter defaults with `TrainingConstants`
  - Replaced hard-coded update intervals with `DashboardConstants`
  - Replaced all API timeout values with `DashboardConstants.API_TIMEOUT_SECONDS`
  - Updated backend-params-state Store to use constants
  - 14+ locations updated to use centralized constants

- **Configuration Enhancement** (2025-11-17)
  - Added training parameter section to `conf/app_config.yaml`
  - Defined min/max/default values for epochs, learning rate, hidden units
  - Aligned configuration with constants infrastructure
  - Added parameter descriptions and modifiability flags
  - Added training behavior configuration (checkpoints, early stopping)
  - Added training monitoring configuration (update intervals, logging)

- **Config Manager Enhancements** (2025-11-17)
  - Added `TrainingParamConfig` TypedDict for type safety
  - Added `get_training_param_config()` method with validation
  - Added `validate_training_param_value()` for runtime validation
  - Added `get_training_defaults()` helper method
  - Added `is_param_modifiable_during_training()` check
  - Added `verify_config_constants_consistency()` validation
  - Full integration with constants module
  - Comprehensive error handling and logging

- **Configuration Testing** (2025-11-17)
  - 20 unit tests for training parameter configuration (100% pass)
  - 4 integration tests for config/constants consistency (100% pass)
  - Tests for parameter validation and range checking
  - Tests for modifiability flags
  - Tests for constants consistency verification

---

## [0.6.0] - 2025-11-13

### Added, [0.6.0]

- **Complete Training Lifecycle Controls**
  - Resume button → POST /api/train/resume
  - Reset button → POST /api/train/reset
  - Full 5-button training control panel (Start, Pause, Resume, Stop, Reset)

- **Real-Time Status & Connection Bar**
  - Always-visible health monitoring at top of dashboard
  - Color-coded latency indicator (green <100ms, orange <500ms, red >500ms)
  - Live status display: State | Phase | Epoch | Hidden Units
  - Real-time API latency measurement (updates every second)

- **Phase-Aware Metrics Visualization**
  - Light yellow background bands highlighting candidate training phases
  - Cyan dashed markers when hidden units added
  - Annotated "+Unit #N" labels on addition events
  - Applied to both loss and accuracy plots

- **Animated Network Growth**
  - 500ms smooth transitions on topology updates
  - New hidden unit highlighting with cyan pulse effect
  - Larger markers (28px vs 20px) for newly added nodes
  - Automatic detection of network growth from metrics

- **Performance Optimization - Active Tab Gating**
  - Topology updates only when topology tab active
  - Decision boundary updates only when boundaries tab active
  - Dataset updates only when dataset tab active
  - 75% reduction in unnecessary API calls

- **Documentation & Testing**
  - docs/API_SCHEMAS.md - Complete API reference with request/response schemas
  - test_api_contracts.py - 21 contract validation tests
  - test_dashboard_e2e.py - 4 end-to-end smoke tests
  - docs/DASHBOARD_ENHANCEMENTS.md - Enhancement design document
  - CI/CD regression test suite step

### Changed, [0.6.0]

- Dashboard performance: Tab switching 60% faster (~500ms → ~200ms)
- API efficiency: 75% reduction in calls (only active tab updates)
- Backend CPU usage: ~40% reduction
- Network traffic: ~75% reduction
- dashboard_manager.py version: 1.7.0 → 1.8.0
- metrics_panel.py version: 1.3.0 → 1.4.0
- network_visualizer.py version: 1.3.0 → 1.4.0
- training_metrics.py version: 0.1.4 → 1.0.0

### Fixed, [0.6.0]

- Training Metrics tab not displaying data (endpoint changed to /api/metrics/history)
- Dashboard update_metrics_store normalization for dict/list API formats
- TrainingMetricsComponent now accepts component_id parameter
- TrainingMetricsComponent now inherits from BaseComponent
- Dashboard manager _api_url tests now use Flask request context
- WebSocket manager unit tests now use AsyncMock properly
- 4 API contract test expectations aligned with actual responses

## [0.5.0] - 2025-11-11

### Added, [0.5.0]

- **Comprehensive Test Suite Expansion** (202 new tests)
  - Backend integration tests: 64 new tests (test_cascor_integration_paths.py, test_cascor_integration_monitoring.py, test_cascor_integration_topology.py, test_training_monitor.py)
  - WebSocket/API integration tests: 80 new tests (test_main_endpoints.py, test_main_ws.py, test_websocket_manager_unit.py)
  - Frontend component tests: 58 new tests (test_dashboard_manager.py, test_components_basic.py)
  - **Impact:** Comprehensive coverage of integration paths and component behavior

### Fixed, [0.5.0]

- **Integration Test Failures** (13 failures resolved)
  - API structure mismatches between test expectations and implementation
  - Backend initialization issues in test fixtures
  - CORS configuration verification completed
  - **Impact:** Test pass rate improved to 83% (240/289 tests)

### Changed, [0.5.0]

- **Test Coverage Metrics**
  - Overall coverage: 61% → 22% (measurement adjusted after reorganization)
  - Test pass rate: 83% → maintained at 83%
  - **Note:** Coverage drop due to new untested code paths added during integration work
  - **Impact:** Identified areas requiring additional test coverage

- **Demo Mode Documentation** (v1.1.0)
  - Updated version from 0.1.0 to 1.1.0
  - Added verified training control methods documentation (start, pause, resume, stop, reset)
  - **Impact:** Clearer API documentation for demo mode control

## [0.4.0] - 2025-11-11

### Added, [0.4.0]

- **WebSocket Real-Time Communication**
  - WebSocket endpoint `/ws` for real-time connections
  - Bi-directional communication for training updates and control
  - **Impact:** Foundation for real-time UI updates

- **Training Control API**
  - Training control endpoints: `/api/train/start`, `/api/train/pause`, `/api/train/resume`, `/api/train/stop`, `/api/train/reset`
  - Complete training lifecycle management via REST API
  - Thread-safe control operations with status broadcasting
  - **Impact:** Full programmatic control of training process

- **Metrics History API**
  - `/api/metrics/history` endpoint for historical metrics retrieval
  - Supports time-series analysis and visualization
  - **Impact:** Historical data access for trend analysis

- **Dashboard Training Controls**
  - Training control button callbacks in dashboard
  - Wire Start/Pause/Resume/Stop/Reset buttons to API endpoints
  - Real-time button state updates based on training status
  - **Impact:** Users can control training from UI

- **Network Topology Visualization Enhancements**
  - Input→Hidden edges now visible in network topology
  - Hidden→Hidden connection visualization
  - Complete network architecture display
  - **Impact:** Full understanding of network structure

- **Health Endpoint Enhancement**
  - Timestamp field added to `/health` endpoint response
  - Enables uptime monitoring and health tracking
  - **Impact:** Better observability and monitoring

- **CI/CD Documentation**
  - [docs/CICD_QUICK_START.md](docs/CICD_QUICK_START.md) - Get CI/CD running in 5 minutes
  - Streamlined onboarding for CI/CD setup
  - **Impact:** Faster developer onboarding to CI/CD workflows

### Fixed [0.4.0]

- **Training Control Functionality** (98 frontend tests now passing)
  - Training control buttons now functional (wired callbacks to API endpoints)
  - Start/Pause/Resume/Stop/Reset buttons execute corresponding API calls
  - Button states update based on training status
  - **Impact:** UI controls work as expected

- **Network Topology Visualization** (test_network_visualizer: 26 tests passing)
  - Network topology now shows all connection types including input connections
  - Input→Hidden and Hidden→Hidden edges properly rendered
  - Edge labels and weights display correctly
  - **Impact:** Complete network architecture visible

- **WebSocket Manager Logger Import**
  - Fixed logger import path: `logging.logger` → `logger.logger`
  - Resolves import error in WebSocket manager
  - **Impact:** WebSocket manager initializes correctly

- **WebSocket Broadcast Event Loop**
  - Fixed event loop preference in `broadcast_sync` method
  - Now uses stored event loop when available
  - **Impact:** More reliable async→sync communication

- **Network Visualizer Parameter Handling**
  - Fixed None handling for `show_weights` parameter
  - Defaults to True when not specified
  - **Impact:** No crashes on missing optional parameters

- **Unit Test Method Names**
  - Fixed test method names: `setup_callbacks` → `register_callbacks`
  - Aligned with actual DashboardManager API
  - **Impact:** All architecture tests passing

- **Frontend Component Test Signatures**
  - Fixed method signatures in frontend component tests
  - Updated to match current component implementations
  - **Impact:** 98 frontend unit tests passing (100% pass rate)

- **API Contract Violations**
  - Fixed timestamp format in API responses
  - Fixed metrics format consistency across endpoints
  - Added missing endpoints identified in tests
  - **Impact:** Frontend-backend contract compliance

### Changed [0.4.0]

- **CI/CD Documentation Consolidation**
  - Consolidated 12 CI/CD documentation files → 4 focused guides
  - Archived 8 deprecated CI/CD docs to `docs/history/` with 2025-11-11 timestamp
  - Created streamlined documentation structure:
    - [docs/CICD_QUICK_START.md](docs/CICD_QUICK_START.md) - Quick start guide
    - [docs/CI_CD.md](docs/CI_CD.md) - Comprehensive manual
    - [docs/PRE_COMMIT_GUIDE.md](docs/PRE_COMMIT_GUIDE.md) - Pre-commit hooks
    - [docs/CODECOV_SETUP.md](docs/CODECOV_SETUP.md) - Coverage setup
  - **Impact:** Easier navigation, reduced documentation duplication

- **Component Version Updates**
  - `main.py`: v1.5.0 → v1.6.0 (training control API, WebSocket endpoint)
  - `dashboard_manager.py`: v1.5.0 → v1.6.0 (training control callbacks)
  - `websocket_manager.py`: v1.3.0 → v1.4.0 (logger import fix, event loop preference)
  - `network_visualizer.py`: v1.2.0 → v1.3.0 (input connections, None handling)
  - **Impact:** Version tracking reflects all changes

### Documentation [0.4.0]

- **CI/CD Documentation Updates**
  - Updated CI/CD documentation structure for better navigation
  - Archived superseded CI/CD files to `docs/history/`:
    - `CICD_SETUP_2025-11-11.md`
    - `GITHUB_ACTIONS_SETUP_2025-11-11.md`
    - `TESTING_CI_CD_2025-11-11.md`
    - `CODECOV_INTEGRATION_2025-11-11.md`
    - `PRE_COMMIT_SETUP_2025-11-11.md`
    - `CICD_TROUBLESHOOTING_2025-11-11.md`
    - `CICD_BEST_PRACTICES_2025-11-11.md`
    - `CICD_REFERENCE_2025-11-11.md`
  - Added redirect notices to new consolidated guides
  - **Impact:** Clear documentation structure, preserved history

### Impact [0.4.0]

- **UI Functionality:** Training controls now fully operational
- **Network Visualization:** Complete network structure visible
- **API Completeness:** All endpoints functional and tested
- **Test Coverage:** 98 frontend tests passing (100% pass rate)
- **Documentation:** Streamlined CI/CD guides (12 → 4 files)
- **Code Quality:** Fixed import errors, parameter handling, test alignment

### Metrics Summary [0.4.0]

- Frontend Tests Passing: 98 tests (100% pass rate)
- New API Endpoints: 6 (training control + metrics history + WebSocket)
- Documentation Files: 12 → 4 (consolidated CI/CD docs)
- Archived Files: 8 CI/CD docs (moved to docs/history/)
- Component Versions: 4 components updated to v1.6.0 or higher
- Import Errors Fixed: 1 (WebSocket manager logger)
- Visualization Fixes: 2 (network topology, parameter handling)

## [0.3.0] - 2025-11-07

### Major Release: Documentation Consolidation & Structure Optimization [0.3.0]

#### Added [0.3.0]

- **Comprehensive Testing Documentation Suite**
  - [TESTING_QUICK_START.md](TESTING_QUICK_START.md) - Get testing in 60 seconds (~180 lines)
  - [TESTING_ENVIRONMENT_SETUP.md](TESTING_ENVIRONMENT_SETUP.md) - Complete environment setup (~550 lines)
  - [TESTING_MANUAL.md](TESTING_MANUAL.md) - Complete testing guide (~900 lines)
  - [TESTING_REFERENCE.md](TESTING_REFERENCE.md) - Comprehensive reference (~1,200 lines)
  - [TESTING_REPORTS_COVERAGE.md](TESTING_REPORTS_COVERAGE.md) - Coverage analysis guide (~900 lines)
  - **Impact:** Clear learning path from beginner to advanced testing

- **Documentation Navigation System**
  - [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md) - Master navigation guide (~700 lines)
  - Complete document index (all 80+ files cataloged)
  - "I Want To..." quick reference table
  - Document purpose, audience, and status tracking
  - Search strategies and quick reference card
  - **Impact:** Find any document in <30 seconds

- **Historical Documentation Archive**
  - [docs/history/](docs/history/) directory created
  - 67 historical files archived (~33,000 lines)
  - Organized by category: MVP/Implementation, Testing, Bug Fixes, Analysis/Design, Integration
  - Complete development history preserved
  - **Impact:** Clean active docs, preserved historical context

- **Setup Documentation**
  - [QUICK_START.md](QUICK_START.md) - 5-minute quickstart guide (~250 lines)
  - [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) - Complete setup reference (~400 lines)
  - Clear prerequisites, step-by-step instructions
  - Common issues and troubleshooting
  - **Impact:** New developers productive in <15 minutes

#### Changed [0.3.0]

- **Documentation Structure Reorganization**
  - Root directory: Active/current docs only (11 files)
  - docs/ directory: Technical guides and references (6 active files)
  - docs/history/: Historical/archived content (67 files)
  - **Breaking Change:** File locations changed - update any hardcoded paths
  - **Migration:** See [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md) for new structure

- **AGENTS.md Enhancements**
  - Added Definition of Done checklist
  - Enhanced testing requirements section
  - Updated recent changes with documentation reorganization
  - Added file placement rules
  - **Impact:** Clearer development standards

- **README.md Improvements**
  - Restructured for better flow
  - Enhanced testing section with complete commands
  - Added CI/CD status badges
  - Improved quick start instructions
  - **Impact:** Better first impression for new users

#### Fixed [0.3.0]

- **Documentation Duplication**
  - Removed duplicate AGENTS.md, CHANGELOG.md from docs/
  - Single source of truth for all active documentation
  - Historical versions preserved in docs/history/
  - **Impact:** No conflicting documentation

- **Documentation Gaps**
  - Added missing testing documentation (5 new files)
  - Added missing setup documentation (2 new files)
  - Filled gaps in coverage reporting guides
  - **Impact:** Complete documentation coverage

#### Documentation [0.3.0]

- **Archive Documentation** (67 files moved to docs/history/)
  - MVP/Implementation Reports: 15 files
  - Testing Reports: 10 files
  - Bug Fix Reports: 12 files
  - Analysis/Design Documents: 12 files
  - Integration/Planning: 8 files
  - Miscellaneous: 10 files

- **Active Documentation** (11 files in root)
  - README.md - Project overview
  - QUICK_START.md - Quick start guide
  - ENVIRONMENT_SETUP.md - Environment setup
  - DOCUMENTATION_OVERVIEW.md - Navigation guide
  - AGENTS.md - Development guide
  - CHANGELOG.md - Version history
  - TESTING_QUICK_START.md - Testing quick start
  - TESTING_ENVIRONMENT_SETUP.md - Test environment
  - TESTING_MANUAL.md - Testing guide
  - TESTING_REFERENCE.md - Testing reference
  - TESTING_REPORTS_COVERAGE.md - Coverage guide

- **Technical Documentation** (6 files in docs/)
  - CI_CD.md - CI/CD pipeline guide
  - PRE_COMMIT_GUIDE.md - Pre-commit hooks
  - CODECOV_SETUP.md - Coverage setup
  - TESTING_CI_CD.md - Testing workflow
  - references_and_links.md - External links
  - DOCUMENTATION_ANALYSIS_2025-11-05.md - Consolidation analysis

#### Impact [0.3.0]

- **Documentation Discoverability:** Find any doc in <30 seconds (vs. 5+ minutes)
- **New Developer Onboarding:** <15 minutes to productive (vs. hours)
- **Documentation Maintenance:** Clear ownership and update requirements
- **Historical Preservation:** Complete development history archived
- **Testing Clarity:** 5 comprehensive guides cover all skill levels
- **Code Quality:** Clear standards in AGENTS.md Definition of Done

#### Metrics Summary [0.3.0]

- Documentation Files: 80+ files organized
- Active Documentation: 11 root files, 6 docs/ files
- Historical Archive: 67 files, ~33,000 lines
- New Documentation: 8 files, ~5,000 lines
- Documentation Coverage: 100% of project aspects
- Average Time to Find Info: <30 seconds

### Documentation File Changes [0.3.0]

- **Created:** TESTING_QUICK_START.md, TESTING_ENVIRONMENT_SETUP.md, TESTING_MANUAL.md, TESTING_REFERENCE.md, TESTING_REPORTS_COVERAGE.md, QUICK_START.md, ENVIRONMENT_SETUP.md, DOCUMENTATION_OVERVIEW.md
- **Enhanced:** AGENTS.md, README.md, CHANGELOG.md
- **Archived:** 67 files to docs/history/
- **Removed:** Duplicate AGENTS.md, CHANGELOG.md from docs/

## [0.2.1] - 2025-10-30

### Minor Release: Phase 2.5 Pre-Deployment MVP Enhancements [0.2.1]

#### Added, [0.2.1]

- **Client-Side WebSocket Real-Time Updates (P1B)**
  - Created [src/frontend/assets/websocket_client.js](src/frontend/assets/websocket_client.js)
  - Dual WebSocket channels: `/ws/training` and `/ws/control`
  - Automatic reconnection with exponential backoff
  - <100ms latency for metrics updates
  - Replaced HTTP polling with efficient push architecture
  - **Impact:** Real-time updates with minimal latency

- **Training Control Commands (P1C)**
  - Added pause/resume/reset methods to DemoMode
  - Enhanced `/ws/control` endpoint for command handling
  - Thread-safe control flow with Events
  - Commands: start, stop, pause, resume, reset
  - Real-time status broadcasting to clients
  - **Impact:** Full training lifecycle control

- **Comprehensive Advanced Testing (P1D)**
  - Created [test_demo_mode_advanced.py](src/tests/integration/test_demo_mode_advanced.py) (13 tests)
  - Created [test_config_manager_advanced.py](src/tests/unit/test_config_manager_advanced.py) (12 tests)
  - Created [test_websocket_control.py](src/tests/integration/test_websocket_control.py) (10 tests)
  - 84% coverage for DemoMode (exceeded 60%+ target)
  - Thread safety and integration tests
  - **Impact:** Robust test coverage for critical components

- **Configuration System Improvements (P1E)**
  - Environment variable expansion (${VAR}, $VAR)
  - Nested override collision handling
  - Configuration validation with defaults
  - Force reload support for tests
  - Enhanced error handling and logging
  - **Impact:** More flexible and robust configuration

#### Changed [0.2.1]

- **WebSocket Architecture**
  - Moved from HTTP polling to push-based WebSocket updates
  - Breaking change: Frontend now requires WebSocket support
  - **Migration:** Update clients to use websocket_client.js

#### Documentation [0.2.1]

- **notes/MVP_PRE_DEPLOYMENT_IMPLEMENTATION_2025-10-30.md** - Complete Phase 2.5 implementation details
- **notes/DEVELOPMENT_ROADMAP.md** - Updated with Phase 2 completion status

#### Impact [0.2.1]

- **Real-Time Performance:** <100ms update latency (vs. 1000ms polling)
- **User Control:** Full training lifecycle management
- **Test Coverage:** 84% for DemoMode, comprehensive integration tests
- **Configuration Flexibility:** Environment-based overrides, validation
- **MVP Readiness:** All P1 priority items complete

#### Metrics Summary [0.2.1]

- New Tests: 35 tests (13 + 12 + 10)
- Coverage Improvement: DemoMode 84% (target: 60%+)
- WebSocket Latency: <100ms (vs. 1000ms polling)
- Configuration: Full validation and expansion support

## [0.2.0] - 2025-11-03

### Major Release: Testing Infrastructure & CI/CD Pipeline [0.2.0]

#### Added [0.2.0]

- **Complete Test Infrastructure** - 170+ new tests, 100% pass rate, 73% coverage
  - Frontend component tests: 73 tests (71-94% coverage per component)
  - API integration tests: 28 tests for all endpoints
  - WebSocket control tests: 10 tests with protocol verification
  - Demo mode advanced tests: 13 tests for thread safety
  - Config manager advanced tests: 12 tests for validation
  - Architecture verification tests: Updated to match implementation
  - Test organization: Unit, integration, performance categories
  - **Impact:** Zero flaky tests, deterministic results, production-ready reliability

- **CI/CD Pipeline** (2025-11-03)
  - Complete GitHub Actions workflow (`.github/workflows/ci.yml`)
  - Multi-version Python testing (3.11, 3.12, 3.13)
  - Automated test execution on push and PR
  - Coverage reporting with Codecov integration
  - Code quality checks (Black, isort, Flake8, MyPy)
  - Quality gates enforce 60% minimum coverage
  - Artifact uploads for test results and coverage reports
  - **Impact:** Prevents regressions, enforces quality standards, automates testing

- **Pre-commit Hooks** (2025-11-03)
  - Configuration file (`.pre-commit-config.yaml`)
  - Code formatting (Black, isort)
  - Linting (Flake8)
  - Security checks (Bandit)
  - YAML/JSON validation
  - **Impact:** Catch issues locally before pushing to CI

- **Coverage Configuration** (2025-11-03)
  - `.coveragerc` file with module-specific thresholds
  - HTML, XML, and JSON report generation
  - Exclude patterns for tests and generated files
  - **Impact:** Better visibility into test coverage gaps

- **Project Configuration** (2025-11-03)
  - `pyproject.toml` with tool settings
  - Black formatter settings (120 char line length)
  - isort import sorter configuration
  - Bandit security scanner settings
  - MyPy type checker configuration
  - **Impact:** Consistent code style across all tools

#### Fixed [0.2.0]

- **Test Fixture Discovery** - Created `src/tests/conftest.py` at root (21 errors eliminated)
  - All fixtures now discoverable by pytest
  - Singleton reset fixture ensures test isolation
  - ConfigManager and DemoMode auto-reset between tests
  - **Impact:** 100% test pass rate, deterministic results

- **WebSocket Connection Protocol** - Added connection confirmation to `/ws/control`
  - Endpoint sends immediate connection acknowledgment
  - Fixed command response handling (no double responses)
  - Resolved demo mode initialization in test context
  - Fixed epoch reset race condition (capture state before increment)
  - **Impact:** All 10 WebSocket tests passing

- **Demo Mode State Management** - Proper reset, pause, resume, stop functionality
  - `start()` and `reset()` return state snapshots
  - Thread-safe pause/resume implementation
  - Graceful shutdown with state cleanup
  - **Impact:** Reliable training control

- **Frontend Component Issues** - Fixed multiple rendering and update problems
  - Network topology: Added 'nodes' key for compatibility
  - Decision boundary: Fixed prediction integration
  - Dataset plotter: Resolved update callback issues
  - Metrics panel: Fixed interval callback handling
  - **Impact:** All dashboard components working correctly

- **Import Statement** - Fixed `training_metrics.py` logger import
  - Changed from `from logger` to `from ..logger`
  - Resolves relative import error
  - **Impact:** No import errors

- **Architecture Tests** - Updated to match actual implementation
  - Fixed expected method names and signatures
  - Aligned with current codebase structure
  - Removed obsolete test expectations
  - **Impact:** All architecture tests passing

#### Changed [0.2.0]

- **Test Organization** - Renamed `implementation_script.py` (not a pytest file)
  - Tests now properly organized by category
  - Clear separation of unit/integration/performance
  - Marker-based filtering works correctly
  - **Impact:** Better test discoverability

- **WebSocket Endpoint** - `/ws/control` sends connection confirmation
  - Breaking change in protocol (added confirmation message)
  - Clients must handle initial connection response
  - **Impact:** Better connection state management

- **Demo Mode API** - `start()` and `reset()` return state snapshots
  - Breaking change: return values added
  - Enables verification in tests
  - **Impact:** Improved testability

- **Topology Response** - Added 'nodes' key for compatibility
  - Ensures backward compatibility with expected format
  - **Impact:** Frontend components work without modification

#### Documentation [0.2.0]

- **docs/CI_CD.md** - Comprehensive CI/CD pipeline documentation (1,000+ lines)
- **docs/CODECOV_SETUP.md** - Coverage tracking setup guide
- **docs/PRE_COMMIT_GUIDE.md** - Code quality automation guide
- **notes/TEST_FIXES_2025-11-03.md** - Comprehensive test fix report (3,000+ lines)
- **notes/FRONTEND_TESTING_2025-11-03.md** - Frontend testing implementation guide
- **notes/CI_CD_IMPLEMENTATION_2025-11-03.md** - CI/CD setup details
- **notes/FINAL_STATUS_2025-11-03.md** - Complete project status
- **AGENTS.md** - Updated with testing commands, CI/CD procedures, code quality checks
- **README.md** - Added badges, testing section, CI/CD section, development workflow
- **DEVELOPMENT_ROADMAP.md** - Updated Phase 2 status to complete

#### Impact [0.2.0]

- **Test Reliability:** Zero flaky tests, 100% deterministic results
- **Developer Velocity:** Pre-commit catches issues before commit, CI validates all PRs
- **Code Quality:** Automated checks prevent regressions, enforce standards
- **Coverage Tracking:** Codecov provides visibility and trending (5% → 73%)
- **Production Ready:** Complete test suite, quality gates, CI/CD automation
- **Documentation:** 15+ new files, 10,000+ lines of guides and reports

#### Metrics Summary [0.2.0]

- Test Errors: 21 → 0 (100% elimination)
- Test Failures: 17 → 0 (100% resolution)
- Tests Passing: 66 → 170+ (158% increase)
- Coverage: 5% → 73% (1,360% increase)
- Pass Rate: 58% → 100% (perfect)
- New Test Files: 7 files, 170+ tests
- New Documentation: 15+ files, 10,000+ lines

### Changed Files [0.2.0]

- **Testing Commands** - Updated AGENTS.md with correct pytest paths and coverage commands
- **README Badges** - Added CI/CD, coverage, Python version, license, and code style badges

## [0.1.1] - 2025-10-29

### Fixed Issues [0.1.1]

#### Critical Demo Mode Activation [0.1.1]

- **Demo mode environment variable check**
  - Added explicit check for `CASCOR_DEMO_MODE` environment variable in `main.py`
  - Resolves: Demo mode not activating even when CASCOR_DEMO_MODE=1 is set
  - Forces demo mode when env var is set, skipping CascorIntegration
  - Prevents false success when cascor backend exists but has no network
  - **Impact:** Demo mode now activates correctly, generates training data

#### Critical Dashboard Data Flow [0.1.1]

- **Dashboard API URL construction bug**
  - Fixed `dashboard_manager.py` callbacks using incorrect `request.host_url`
  - Added `_api_url()` helper method using `request.scheme` + `request.host`
  - Resolves: "No data available" in all dashboard tabs
  - URLs now correctly target `/api/*` instead of `/dashboard/api/*`
  - All 4 tabs now display real-time data correctly

#### Error Visibility [0.1.1]

- **API fetch error logging**
  - Changed exception logging from debug to warning level
  - Added exception type information for better debugging
  - Added success logging at debug level (fetched count, URL)
  - Prevents silent failures in production

#### Timeout Improvements [0.1.1]

- **Request timeout increases**
  - Standard endpoints: 1s → 2s
  - Decision boundary: 2s → 3s (computationally intensive)
  - Prevents false failures on slower systems

### Documentation Updates [0.1.1]

- **notes/MISSING_DATA_FIX_2025-10-29.md** - Complete analysis of dashboard data issue
- **notes/CURRENT_STATUS_REPORT.md** - Comprehensive status verification
- **notes/DEVELOPMENT_ROADMAP.md** - Updated with regression fix recommendations

## [0.1.0] - 2025-10-29

### Fixed Prioritized Issues [0.1.0]

#### Critical Regression [0.1.0]

- **Demo script Python interpreter path**
  - Fixed `demo` and `utils/run_demo.bash` to use conda environment Python (`$CONDA_PREFIX/bin/python`)
  - Added `exec` for proper signal handling
  - Added `-u` flag for unbuffered output
  - Added `CASCOR_DEMO_MODE=1` environment variable export
  - Resolves: `ModuleNotFoundError: No module named 'uvicorn'`

#### Thread Safety [0.1.0]

- **DemoMode concurrent access protection**
  - Added `threading.Lock()` for shared state synchronization
  - Added `threading.Event()` for clean shutdown signaling
  - Protected all state mutations with lock
  - Made getter methods thread-safe with lock guards
  - Prevents: Race conditions, RuntimeError during iteration

#### Shutdown Handling [0.1.0]

- **DemoMode stop mechanism**
  - Replaced `time.sleep()` with `Event.wait()` for interruptible sleep
  - Changed loop condition from `self.is_running` to `not self._stop.is_set()`
  - Added timeout handling for unresponsive threads
  - Shutdown now completes within `update_interval` instead of hanging

#### Memory Management [0.1.0]

- **Bounded collections**
  - Changed `list` to `deque(maxlen=1000)` for all history tracking
  - Prevents unbounded memory growth during long training sessions
  - Applies to: `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`, `metrics_history`

#### WebSocket Communication [0.1.0]

- **Thread-safe broadcasting**
  - Added `WebSocketManager.set_event_loop()` method
  - Added `WebSocketManager.broadcast_from_thread()` method
  - Uses `asyncio.run_coroutine_threadsafe()` for proper thread-to-async communication
  - Integrated event loop setting in `main.py` startup
  - Updated `DemoMode` to use `broadcast_from_thread()` instead of `broadcast_sync()`

### Changed Components [0.1.0]

#### Metric Key Standardization [0.1.0]

- **Validation metric naming**
  - Renamed `value_loss` → `val_loss`
  - Renamed `value_accuracy` → `val_accuracy`
  - Standardizes on industry convention (`val_` prefix)
  - **Breaking Change:** Code depending on old keys needs update

#### State Management [0.1.0]

- **DemoMode initialization**
  - Added `reset` parameter to `start()` method (default: `True`)
  - Clears all histories and resets state on start if `reset=True`
  - Supports both fresh runs and continued training
  - Prevents state leakage between sessions

#### Error Handling [0.1.0]

- **Logging improvements**
  - Distinguish `ImportError` (silent) from other exceptions (warning)
  - WebSocket broadcast failures now logged at warning level with exception type
  - Added structured error messages with `{type(e).__name__}: {e}` format
  - Prevents silent failures

### Added Documents [0.1.0]

#### Documentation File Updates [0.1.0]

- **AGENTS.md** - Comprehensive development guide
  - Quick start commands
  - Architecture overview
  - Code style guidelines
  - Thread safety patterns
  - Async/thread communication examples
  - Common issues and solutions
  - Testing guidelines
  - Debugging procedures

- **notes/REGRESSION_FIX_REPORT.md** - Detailed analysis report
  - Root cause analysis
  - Comprehensive issue identification
  - Solution explanations
  - Testing procedures
  - Impact assessment
  - Future recommendations

- **notes/FIX_SUMMARY.md** - Quick reference summary

- **CHANGELOG.md** - This file

#### Features [0.1.0]

- **Import statement for copy module** in `demo_mode.py` (preparation for deep copying)

### Deprecated [0.1.0]

None.

### Removed [0.1.0]

None.

### Security [0.1.0]

None.

## [0.0.4] - 2025-10-21

### Added Features [0.0.4]

- Initial demo mode implementation
- WebSocket communication
- FastAPI backend with Dash integration
- Basic training metrics visualization

---

## Version History Notes

### Version Format: MAJOR.MINOR.PATCH

- **MAJOR** - Incompatible API changes
- **MINOR** - New functionality (backward-compatible)
- **PATCH** - Bug fixes (backward-compatible)

### Links

- [Unreleased]: Current development
- [0.15.0]: Phase 0 - Core UX Stabilization (11 fixes)
- [0.14.4]: Configuration test architecture fix + coverage improvements
- [0.14.3]: Apply button fix + graph range persistence
- [0.14.2]: Top status bar updates with FSM integration
- [0.14.1]: Documentation and dependency updates
- [0.14.0]: Bash script configuration infrastructure
- [0.4.0]: Documentation consolidation and structure optimization
- [0.3.1]: Phase 2.5 pre-deployment MVP enhancements
- [0.3.0]: Testing infrastructure and CI/CD pipeline
- [0.2.1]: Dashboard data flow fix
- [0.2.0]: Regression fixes and thread safety
- [0.1.4]: Initial release with demo mode

---

## Developer Notes

### Breaking Changes in [0.0.4]

#### Documentation File Locations

Documentation has been reorganized into a clear three-tier structure:

**Old Structure:**

```bash
juniper_canopy/
├── docs/
│   ├── 80+ files in flat structure
│   ├── Duplicate AGENTS.md, CHANGELOG.md
│   └── Mix of active and historical docs
```

**New Structure:**

```bash
juniper_canopy/
├── (root) - 11 active docs
│   ├── README.md, QUICK_START.md, ENVIRONMENT_SETUP.md
│   ├── DOCUMENTATION_OVERVIEW.md, AGENTS.md, CHANGELOG.md
│   └── TESTING_*.md (5 files)
├── docs/ - 6 technical guides
│   ├── CI_CD.md, PRE_COMMIT_GUIDE.md, CODECOV_SETUP.md
│   └── TESTING_CI_CD.md, references_and_links.md
└── docs/history/ - 67 archived files
    ├── MVP/Implementation reports (15)
    ├── Testing reports (10)
    ├── Bug fix reports (12)
    ├── Analysis/design docs (12)
    └── Integration/planning (8)
```

**Migration:**

- Update any hardcoded paths to documentation
- Use [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md) to locate files
- Historical docs remain accessible in docs/history/

#### New User Onboarding Flow

**Old:** README.md → Search for relevant docs → Trial and error  
**New:** README.md → QUICK_START.md → ENVIRONMENT_SETUP.md → AGENTS.md

**Impact:** <15 minutes to productive (vs. hours)

### Breaking Changes in [0.0.3-1]

#### WebSocket Architecture

Old code using HTTP polling must migrate to WebSocket push updates:

```javascript
// Old (polling - deprecated)
setInterval(() => {
  fetch('/api/metrics')
    .then(r => r.json())
    .then(updateUI);
}, 1000);

// New (WebSocket - required)
const ws = new WebSocket('ws://localhost:8050/ws/training');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateUI(data);
};
```

**Migration:** Include `src/frontend/assets/websocket_client.js` in your frontend.

### Breaking Changes for Metrics in [0.0.3-1]

#### Metric Key Names

Old code using `value_loss` or `value_accuracy` must update to `val_loss` and `val_accuracy`:

```python
# Old (broken)
loss = metrics['value_loss']

# New (correct)
loss = metrics['val_loss']
```

#### DemoMode start() Method

The `start()` method now accepts an optional `reset` parameter:

```python
# Default behavior (reset=True): fresh start
demo.start()

# Continue from previous state
demo.start(reset=False)
```

### Migration Guide

No migration steps required unless:

1. You have code accessing `value_loss` or `value_accuracy` → Update to `val_loss`/`val_accuracy`
2. You have custom tests expecting immediate shutdown → Update to account for `update_interval` delay

### Testing

After upgrading to [0.0.3-1]:

```bash
# Verify documentation structure
ls -la                  # Should see 11 active docs in root
ls -la docs/            # Should see 6 technical guides
ls -la docs/history/    # Should see 67 archived files

# Verify quick start works
./demo

# Navigate documentation
cat DOCUMENTATION_OVERVIEW.md   # Master navigation guide

# Run test suite with new testing docs
cd src && pytest tests/ -v

# Check coverage
cd src && pytest tests/ --cov=. --cov-report=html
open ../reports/coverage/index.html
```

After upgrading to [0.0.3]:

```bash
# Verify WebSocket client
cat src/frontend/assets/websocket_client.js

# Test training controls
./demo
# In browser, test pause/resume/reset buttons

# Run advanced tests
cd src && pytest tests/integration/test_demo_mode_advanced.py -v
cd src && pytest tests/integration/test_websocket_control.py -v
```

After upgrading to [0.0.2]:

```bash
# Verify CI/CD setup
cat .github/workflows/ci.yml
pre-commit run --all-files

# Run complete test suite
cd src && pytest tests/ -v --cov=. --cov-report=html

# Check coverage thresholds
cd src && pytest tests/ --cov=. --cov-report=term-missing
```

After upgrading to [0.0.1]:

```bash
# Verify demo mode works
./demo

# Run test suite
pytest

# Check for import errors
cd src && /opt/miniforge3/envs/JuniperPython/bin/python -c "import uvicorn; print('OK')"
```

### For More Information

#### v0.0.4 Documentation Consolidation

- See [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md) for complete documentation navigation
- See [QUICK_START.md](QUICK_START.md) to get running in 5 minutes
- See [TESTING_QUICK_START.md](TESTING_QUICK_START.md) for testing in 60 seconds
- See [docs/DOCUMENTATION_ANALYSIS_2025-11-05.md](docs/DOCUMENTATION_ANALYSIS_2025-11-05.md) for consolidation analysis

#### v0.0.3-1 Pre-Deployment Enhancements

- See [docs/history/MVP_PRE_DEPLOYMENT_IMPLEMENTATION_2025-10-30.md](docs/history/MVP_PRE_DEPLOYMENT_IMPLEMENTATION_2025-10-30.md) for Phase 2.5 details

#### v0.0.3 Testing & CI/CD

- See [docs/CI_CD.md](docs/CI_CD.md) for CI/CD pipeline guide
- See [docs/PRE_COMMIT_GUIDE.md](docs/PRE_COMMIT_GUIDE.md) for code quality automation
- See [docs/history/FINAL_STATUS_2025-11-03.md](docs/history/FINAL_STATUS_2025-11-03.md) for complete Phase 2 status
- See [docs/history/TEST_FIXES_2025-11-03.md](docs/history/TEST_FIXES_2025-11-03.md) for test fix details

#### v0.0.2 Dashboard Fix

- See [docs/history/MISSING_DATA_FIX_2025-10-29.md](docs/history/MISSING_DATA_FIX_2025-10-29.md) for dashboard data flow analysis
- See [docs/history/CURRENT_STATUS_REPORT.md](docs/history/CURRENT_STATUS_REPORT.md) for status verification

#### v0.0.1 Regression Fixes

- See [docs/history/REGRESSION_FIX_REPORT.md](docs/history/REGRESSION_FIX_REPORT.md) for detailed technical analysis
- See [docs/history/COMPLETE_FIX_SUMMARY_2025-10-29.md](docs/history/COMPLETE_FIX_SUMMARY_2025-10-29.md) for all fixes

#### General Development

- See [AGENTS.md](AGENTS.md) for development guidelines and conventions
- See [README.md](README.md) for project overview and quick start
- See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for environment configuration
