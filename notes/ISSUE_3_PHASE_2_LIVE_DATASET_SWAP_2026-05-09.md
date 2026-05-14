# Issue #3 Phase 2 — Live Dataset Switch (2026-05-09)

* **Author**: Paul Calnon (drafted by Claude Code Opus 4.7)
* **Status**: Approved — design decisions resolved 2026-05-10 (see Appendix A for design discussion)
* **Last updated**: 2026-05-10
* **Parent plan**: [`FRONTEND_ISSUES_PLAN_2026-05-09.md`](./FRONTEND_ISSUES_PLAN_2026-05-09.md) §3.5.2 / §3.6.2 / §3.8
* **Authoritative source for**: in-flight (live) dataset swap, experimental-functions gate, two-step warning modal, History / Snapshots / Replay persistence of dataset-swap events.
* **Out of scope here**: cold-swap dataset behavior (Phase 1 — already covered by parent plan PR-6/PR-7), generic param map work (parent plan §1).

> **Source-of-truth precedence (per parent §3.4.2):** the underlying functional requirements from §3.4.2 are authoritative.
> Specific endpoint shapes, persistence schemas, and UI mechanics in this document are starting points and may be adjusted during review without invalidating the plan.

---

## 1. Why a Phase 2

Phase 1 (parent plan PR-6/PR-7 + the §3.5.2 Cancel button) resolves the user-visible Issue #3 bug: "Dataset View tab edits don't change the training dataset".
That fix follows the cold-swap path — apply, restart, train on the new dataset.

The §3.4.2 alternate approach explicitly calls out a second requirement: **CasCor cross-training experiments** need the ability to switch the dataset *mid-training* without tearing down the network, and to have the resulting History / Snapshots / Replay reflect the swap.
That is Phase 2.

The two phases ship independently because:

1. The cascor surface area for live swap touches lifecycle, persistence, and candidate-pool reconstruction — too large to land alongside Phase 1.
2. Phase 1 alone resolves the reported bug.
3. The experimental flag and warning copy benefit from a UX review pass that shouldn't block the Phase 1 cold-swap fix.

---

## 2. Functional requirements (§3.4.2 source of truth)

| #     | Requirement                                                                                                                       |
|-------|-----------------------------------------------------------------------------------------------------------------------------------|
| F2.1  | A user shall be able to switch the live training dataset without first stopping training.                                         |
| F2.2  | The live-switch path shall be gated behind an explicit "Enable Experimental Functions" user opt-in.                               |
| F2.3  | While experimental functions are disabled, all live-switch UI affordances shall be disabled / greyed.                             |
| F2.4  | Activating the live switch shall require a second opt-in: an explicit warning, then explicit Accept.                              |
| F2.5  | The user shall always be able to back out of the live-switch path and use Stop+Restart instead.                                   |
| F2.6  | A live dataset swap may alter the network architecture (candidate pool, output head). This is allowed.                            |
| F2.7  | Training History shall record the dataset swap as a first-class event with timestamp + before/after cfg.                          |
| F2.8  | A snapshot shall be captured at the swap point so the pre-swap state is recoverable.                                              |
| F2.9  | Training Replay shall be able to play back a session that includes a dataset swap (and any architecture changes triggered by it). |
| F2.10 | The server shall enforce the experimental-functions gate; a stale frontend shall not be able to bypass it.                        |

Implementation suggestions below are designed to satisfy these requirements.
Reviewers may adjust mechanics so long as F2.1–F2.10 remain satisfied.

---

## 3. Cascor side

> **Surface reality vs. original draft**: the original §3.2 of this document referenced
> helper components — `snapshot_manager`, `architecture_manager`, `training_history`,
> `status_publisher`, `_wait_until_paused`, `is_training_running`, `_dataset_config_snapshot` —
> that **do not exist** in the cascor codebase as of 2026-05-10. The 2026-05-10 design review
> (Appendix A) replaced the original idealized diff with the design below. The actual cascor
> surface this work builds on is: `state_machine.is_paused()` / `is_started()` / `is_replaying()`,
> `_pause_event`, `_pending_dataset_config`, `_reload_dataset`, `_training_lock`,
> `_train_x` / `_train_y` / `_val_x` / `_val_y`, and the `_executor.submit(_run_training, ...)`
> pattern at `src/api/lifecycle/manager.py:1928`. Any new components introduced below are
> explicitly named (e.g. `architecture_adapter`, `_swap_in_progress`).

### 3.1 Configuration flag

```diff
--- a/src/api/lifecycle/manager.py
+++ b/src/api/lifecycle/manager.py
@@ class CascorLifecycleManager
+    # Set via env var CASCOR_EXPERIMENTAL_FUNCTIONS_ENABLED=1 or via the
+    # admin REST surface. Defaults False so a stale frontend toggle alone
+    # cannot bypass the gate.
+    self._experimental_functions_enabled: bool = (
+        os.environ.get("CASCOR_EXPERIMENTAL_FUNCTIONS_ENABLED") == "1"
+    )
+
+def set_experimental_functions(self, enabled: bool) -> Dict[str, Any]:
+    self._experimental_functions_enabled = bool(enabled)
+    return {"experimental_functions_enabled": self._experimental_functions_enabled}
+
+def get_experimental_functions(self) -> bool:
+    return self._experimental_functions_enabled
```

### 3.2 Live-swap lifecycle method (`swap_dataset_live`)

The method orchestrates a pause → reload → architecture-adapt → restart-in-output-mode → resume sequence.
The training thread is **stopped and resubmitted**, not pause-and-continued, because the in-flight
`network.fit()` closure holds the original tensor refs (`manager.py:1928`) and would not see the swap
otherwise. The user-visible semantic is "pause-and-continue with new dataset"; the runtime semantic
is "controlled stop + restart with preserved network state (weights + cascade structure)."

**Pre-conditions:**

| Condition                              | Failure mode                                    |
|----------------------------------------|-------------------------------------------------|
| Experimental-functions gate enabled    | 403 `experimental_functions_disabled`           |
| Training is currently running          | 422 `training_not_running` (use cold swap)      |
| No swap currently in progress          | 409 `swap_already_in_progress`                  |
| Dim change supported by current PR set | 422 `dim_change_unsupported` (P2-1a/1b only)    |
| Shrink supported by current PR set     | 422 `shrink_unsupported` (P2-1a/1b/1c only)     |

**High-level flow:**

```text
 1. Acquire _training_lock.
 2. Validate gate (403) and is_started() (422).
 3. Set _swap_in_progress = True (subsequent swap requests get 409 from §3.3).
 4. Snapshot pre-swap mutable state for rollback (§3.7 guardrail #1):
       a. Refs to _train_x / _train_y / _val_x / _val_y.
       b. network.state_dict() (weights + buffers).
       c. Current dataset_cfg (the canonical dict used by _reload_dataset).
       d. Current network input_size / output_size.
 5. Pause: _pause_event.clear(); _wait_until_paused(timeout_s=10) → 504 on timeout.
    REQUIRES P2-PRE-1 (pause is non-functional in cascor today; see §3.4 audit).
 6. Stop the training future (signal _stop_requested; await future.result()).
    REQUIRES P2-PRE-1 (stop is similarly non-functional; see §3.4 audit).
 7. Fetch new dataset via _reload_dataset (mutates _train_x/_y/_val_x/_val_y).
    Lock is held throughout — Audit #2 confirmed read-side routes do not contend
    on _training_lock, so a 5–30s fetch under the lock does not freeze the
    canopy status panel. (Earlier draft proposed release/reacquire; unnecessary.)
 8. Compute architecture delta vs. current network I/O dim:
       - Equal-dim: no architecture work.
       - Grow only: append nodes to outermost input/output layer (P2-1c).
       - Shrink (any dim): prepend new dataset-side adapter layer (P2-1d).
 9. Invoke architecture_adapter.adapt_for_dataset_swap(network, before, after) (§3.6).
10. Reset _auto_snap_best_metric (§3.7 guardrail #6).
11. Drop the candidate pool (§3.5 — Option C: abandon all candidates).
12. Submit a new training future with mode="output_training_first" forcing immediate
    output training on the new dataset before any new candidate-pool training.
13. Resume: _pause_event.set().
14. Force topology rebroadcast via the existing WebSocket path (§3.7 guardrail #7).
15. Clear _swap_in_progress.
16. Return structured response (§3.3).

On ANY failure between steps 4 and 14: restore from step-4 snapshot, resume training on
the OLD dataset, clear _swap_in_progress, return 5xx with the original error wrapped.
See §3.8 for the failure-handling contract.
```

**New helpers introduced by this method:**

* `architecture_adapter.adapt_for_dataset_swap(network, before, after) -> ArchChanges` — see §3.6.
* `_wait_until_paused(timeout_s)` — blocks until the training thread reports `_pause_event`
  was observed cleared. May be added if no equivalent exists (depends on §3.4 pause-boundary audit).
* `_swap_in_progress: bool` — module-private flag, mutated under `_training_lock`.
* New `mode="output_training_first"` flag for `_run_training` / `network.fit` so the new training
  future enters output-training mode immediately on the new dataset (§3.5 rationale).

### 3.3 REST surface

```text
POST   /v1/training/dataset/live           — initiate live swap (P2-1a; rejects dim changes 422 until P2-1c/1d)
DELETE /v1/training/dataset/live           — cancel an in-flight swap (P2-1b)
GET    /v1/admin/experimental_functions    — read gate state
POST   /v1/admin/experimental_functions    — toggle gate (server is authoritative per F2.10)
```

**Status codes** (per §3.2): `200 / 403 / 409 / 422 / 504 / 5xx`.

**Response body for `POST /v1/training/dataset/live`** (per §3.7 guardrail #8):

```json
{
  "status": "swapped",
  "before_cfg": {"dataset_type": "spirals", "n_spirals": 2},
  "after_cfg": {"dataset_type": "moons", "noise": 0.2},
  "arch_changes": {
    "input_delta": 0,
    "output_delta": 0,
    "hidden_preserved": 5,
    "abandoned_candidate_pool_size": 8,
    "appended_nodes": {"input": 0, "output": 0},
    "prepended_layers": [],
    "active_output_dim": 2
  },
  "mode": "output_training_first"
}
```

> **REDESIGNED 2026-05-13 (P2-1d)** — the `arch_changes` block reflects the resize+pad
> design that replaced §3.6's prepend-adapter approach.
>
> * `input_delta` / `output_delta` are the *dataset-vs-pre-swap* deltas and may be
>   **negative** on a shrink (the dataset is smaller than the pre-swap network).
> * `appended_nodes.input` / `appended_nodes.output` are the *network-side* growth
>   counts. Zero on a pure shrink (network never shrinks; dataset is zero-padded).
> * `prepended_layers` is a stable **empty list** — no adapter layers are ever
>   prepended in the new design. Preserved as a forward-compatible no-op field
>   so canopy P2-5/P2-6 consumers can rely on the shape.
> * `active_output_dim` is new in P2-1d: the live count of "real" output dims
>   after a dataset shrink. The training loop uses it to mask loss to those
>   dims, avoiding zero-target drift on the padded tail. Equals
>   `network.output_size` when no shrink is active.
>
> See [`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md) for the full implementation contract.

The admin route is access-controlled separately (existing `JUNIPER_DATA_API_KEY` mechanism or
equivalent). Setting it from the canopy UI is **also** behind the client-side experimental
toggle, so the user-facing path is two-gated by construction.

### 3.4 Pre-implementation investigations — RESOLVED 2026-05-10

Both audits ran 2026-05-10 against `juniper-cascor` HEAD `2069930`. Findings:

* **Pause-boundary audit — DEFECT FOUND.** `_pause_event` is set/cleared by manager-layer
  routes (`manager.py:985, 1887, 1953, 1963, 1997`) but is **never `.wait()`-ed inside
  `cascade_correlation.fit()` or any inner training loop**. There are zero references to
  `Event` / `wait` / `pause` / `threading` in `cascade_correlation.py`. `_stop_requested.is_set()`
  is checked only **after** `original_fit()` returns (`manager.py:1457`), by which point fit
  has run to natural completion. The two callbacks wired into the training loop
  (`_output_training_callback` at `manager.py:1373`, `_grow_iteration_callback` at
  `manager.py:1577`) are pure metric-emission sinks — they never raise or block on signals.

  **Result**: clicking Pause or Stop in the UI updates the FSM and broadcasts the new state,
  but training continues to natural completion. **`pause_training` and `stop_training` REST
  endpoints are functionally non-operative.** This is a separate production defect affecting
  every user.

  **Fix**: shipped as **P2-PRE-1** (cascor PR — `fix/pause-stop-noop-defect-2026-05-10`).
  Threads `_stop_requested` and `_pause_event` checks into `_output_training_callback` and
  `_grow_iteration_callback`; defines a `TrainingInterrupted` sentinel that `monitored_fit`
  catches as a clean termination. P2-1a depends on P2-PRE-1.

* **Lock-during-fetch audit — NOT AN ISSUE.** Verified that **none** of the read-side routes
  (`get_status`, `get_metrics`, `get_metrics_history`, `get_dataset`, `get_dataset_data`,
  `get_topology`, `get_training_params`, `get_pending_dataset_config`, `get_network_info`,
  `has_training_data`) acquire `_training_lock`. A 5–30 s juniper-data fetch under the lock
  does **not** freeze the canopy status panel.

  **Design implication**: the original §3.2 release/reacquire pattern (steps 7–9 in the
  pre-2026-05-10 draft) is unnecessary. The lock is held for the entire swap. P2-1b's
  scope is reduced — the "lock-during-fetch fix" line item is dropped (see §7).

### 3.5 Mode-aware swap semantics

The swap policy depends on the training mode at swap time:

* **Output training mode** — pause is safe (output gradient descent is interruptible). After
  swap, the new training future restarts in output-training mode on the new dataset's first
  minibatch / epoch.
* **Candidate training mode** — the candidate pool is being trained against the residual error
  from the **old** output layer. That error signal is meaningless once the dataset changes;
  any further candidate training would correlate against a target that no longer exists,
  risking negative transfer if such candidates were promoted to the cascade. **The entire
  candidate pool is abandoned** (Option C of three considered options; full rationale in
  Appendix A). The swap immediately transitions to output training on the new dataset.

The number of abandoned candidates is reported in the response (`abandoned_candidate_pool_size`)
for observability — UI can surface "Swap discarded N in-flight candidates."

### 3.6 Resize + dataset-pad (REDESIGNED 2026-05-13 — supersedes the prepend-adapter approach)

> **REDESIGN NOTICE (2026-05-13).** The prepend-input-adapter / append-output-adapter design
> originally captured in this section was abandoned during P2-1d implementation. The accumulated
> complexity (new layer type plumbed through forward pass + snapshots + replay + history;
> day-1 zero-init signal-flow collapse on shrink; sequential-composition bookkeeping) was
> moving the network model away from Paul's long-term goals at every step. **The current
> design is the "resize + pad" approach below, locked-in 2026-05-13.** The original
> adapter-layer text is preserved verbatim as **Appendix B** for historical context.
>
> Full implementation contract: [`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md).

**Core principle**: the network is **monotonically non-decreasing** on both `input_size` and
`output_size`. It never shrinks.

| Dataset dim vs network dim | Action | Initialization |
| :--- | :--- | :--- |
| `dataset == network` | No-op | — |
| `dataset > network` | **Grow** the network's dim in place | Random × `random_value_scale` (matches construction-time pattern) |
| `dataset < network` | **Zero-pad the dataset** up to network's dim | — (training-side masking handles the dead slots) |

**Grow** is implemented as a single in-place tensor expansion:

* `output_weights` row-insertion at index `self.input_size` for input grow (preserves the
  `[raw_inputs | hidden_outputs]` layout consumed by `forward()`); column-append for output
  grow.
* `output_bias` element-append for output grow.
* Each `hidden_units[i]["weights"]` mirrors the row-insertion at index `self.input_size`.
  Hidden-unit biases (per-unit scalars) are untouched.
* All new entries random-init × `self.random_value_scale`.
* No new layers; the cascade topology is unchanged. Hidden units and their inter-cascade
  connections are preserved unchanged (same guarantee as the original §3.6 text).

**Shrink** is handled at the dataset boundary, not the network:

* `_train_x` / `_val_x` get zero columns appended up to `network.input_size`.
* `_train_y` / `_val_y` get zero columns appended up to `network.output_size`.
* The lifecycle sets `network.active_output_dim` to the dataset's real output dim so
  `train_output_layer` masks loss to `output[:, :active_output_dim]` and
  `calculate_residual_error` zeroes residual columns past that boundary (preventing
  candidate-training from correlating against zero-padded target signal).

**Mixed** swaps (input grows AND output shrinks, or any other combination) are supported by
side-independent composition: grow on the side that exceeds capacity, pad on the side that
falls short. The two sides do not interact.

**Sides**: the "active" input/output dims that the network learns from at any given moment
are the smaller of (dataset dim, network dim). The network's structural capacity may exceed
the active dims after a shrink — that latent capacity is preserved and made meaningful again
the next time a swap brings a larger dataset.

The trade-off vs the original adapter-layer design:

* **Lost**: exact preservation of the pre-swap forward pass under a grow (P2-1c's zero-init
  invariant). Gradient descent immediately perturbs the new random-init connections.
* **Gained**: no new layer types; cascade architecture stays as-is; snapshot / replay /
  history layers see no topology changes; forward pass adds zero new code paths; the failure
  mode "model produces literal zeros on day 1 after shrink" is eliminated.

### 3.7 Guardrails

All implementations of `swap_dataset_live` must satisfy:

1. **Pre-swap snapshot of mutable state** — copy refs to `_train_x/_y/_val_x/_val_y` and
   the current dataset cfg, plus **clones of the network's parameter tensors**
   (`output_weights`, `output_bias`, each `hidden_units[i]["weights"]`) and the live
   `input_size`, `output_size`, `active_output_dim` bookkeeping. The cascade-correlation
   network has no `state_dict()` (it doesn't inherit from `nn.Module`), so the
   snapshot captures each tensor directly. Used for rollback (§3.8).
2. **Hard timeout on pause** — if `_wait_until_paused` does not return within 10 s, abort the
   swap, release `_swap_in_progress`, return 504. Never block forever.
3. **Idempotency / concurrent-swap guard** — `_swap_in_progress` flag rejects competing
   swap requests with 409 Conflict. The flag is set under `_training_lock` and cleared
   in a `finally` block.
4. **Dimension sanity check** — reject the swap if new `input_dim` or `output_dim` is `<= 0`
   or exceeds a configurable cap (default `2048` for both, exposed via env var or
   `CascorConfig`).
5. **Structured log line** — emit at INFO on completion, e.g.:
   `swap: input 2→3, output 2→2, hidden 5 preserved, candidates 8 abandoned, mode→output_training`.
6. **Reset `_auto_snap_best_metric`** — clear analogous to the fresh-start branch at
   `manager.py:1898–1900`. Otherwise post-swap "best" comparisons compare against a stale
   metric scale and auto-snap stops firing.
7. **Topology rebroadcast** — always force a full topology WebSocket broadcast on swap
   completion (no-op for equal-dim; necessary for grow/shrink). Same surface as the
   `cascade_add` count-only-stub fix shipped in cascor #238.
8. **Structured return shape** — see §3.3 response body. Gives canopy enough to populate
   the timeline marker without a follow-up GET.

### 3.8 Failure handling

If any step between snapshot capture (§3.2 step 4) and topology rebroadcast (§3.2 step 14)
raises:

1. **Restore** `_train_x/_y/_val_x/_val_y` refs from the pre-swap snapshot.
2. **Restore** the network's parameter tensors from the pre-swap snapshot clones —
   `output_weights`, `output_bias`, each `hidden_units[i]["weights"]` — plus the
   `input_size`, `output_size`, `active_output_dim` bookkeeping. (Cascade-correlation
   has no `state_dict()`; the snapshot owns per-tensor clones.) `requires_grad_(True)`
   is re-enabled on `output_weights` and `output_bias` so the next `train_output_layer`
   call rebuilds an optimizer on a leaf tensor; hidden-unit weights stay detached per
   the cascade-correlation freeze convention.
3. **Resume training** on the OLD dataset by submitting a new training future (mode preserved
   from pre-swap). The user's session continues uninterrupted from training's perspective.
4. **Clear `_swap_in_progress`** in a `finally` block so subsequent swaps are not blocked.
5. **Return 5xx** with the original exception's message in the `detail` field. Cascor logs
   the exception with full traceback at ERROR level.

Half-swapped state is **never** an acceptable terminal condition. Tests in P2-1a/1b/1c/1d
must each include at least one failure-injection case (juniper-data unreachable, arch-adapt
raises, pause timeout, etc.) verifying full restore.

### 3.9 History / Snapshots / Replay (F2.7 / F2.8 / F2.9)

* **History** (P2-2): a new `event_type="dataset_swap"` is recorded with payload
  `{before_cfg, after_cfg, arch_changes, pre_swap_snapshot_id, post_swap_snapshot_id}`.
  The history serializer (JSON / Cassandra row, depending on backend) must round-trip
  the payload — including the full layered topology in `arch_changes` — unchanged.
* **Snapshots** (P2-3): a pre-swap snapshot is captured before §3.2 step 5, and a post-swap
  snapshot is captured after §3.2 step 14 (per Appendix A §8 Answer 2 — paired diff requires
  both endpoints). The snapshot format must capture the full layered topology including any
  prepended adapter layers (§3.6) so replay can reconstruct exactly.
* **Replay** (P2-3): the replay engine adds a handler for `dataset_swap`:
    1. Load `pre_swap_snapshot_id` snapshot.
    2. Play forward to the swap timestamp.
    3. Apply the same `_reload_dataset(**after_cfg)` + `architecture_adapter.adapt_for_dataset_swap(...)`
       calls (instantaneous transformation per Appendix A §8 Answer 3 — no animation).
    4. Continue replay from the post-swap state.

  This makes playback reproducible across swaps.

---

## 4. Canopy side

### 4.1 Experimental Functions toggle

Add to the sidebar (under Network Information, since it affects the whole session, not a single tab):

```python
dbc.Switch(
    id="experimental-functions-toggle",
    label="Enable Experimental Functions",
    value=False,
    persistence=True, persistence_type="local",  # survives page reload
)
```

A clientside callback writes the value to a `dcc.Store(id="experimental-flags-store", storage_type="local")`.
A server-side callback POSTs the change to `/v1/admin/experimental_functions` so cascor's gate stays in sync — but the server's gate is the authority (F2.10): if the server says no, the UI shows a toast and reverts the toggle.

### 4.2 Live Dataset Switch button (gated)

Adjacent to the existing "Apply Dataset" button on the Dataset View tab:

```python
dbc.Button(
    "Live Dataset Switch",
    id="live-dataset-switch-button",
    color="warning",
    disabled=True,            # default disabled (F2.3)
    className="ms-2",
)
```

Enable callback:

```python
@app.callback(
    Output("live-dataset-switch-button", "disabled"),
    Input("experimental-flags-store", "data"),
    Input("training-status-store", "data"),
)
def _gate_live_switch(flags, status):
    enabled = bool(flags and flags.get("experimental_functions"))
    running = bool(status and status.get("phase") == "running")
    # Live swap only makes sense while training is running (F2.5 fallback).
    return not (enabled and running)
```

### 4.3 Two-step warning modal (F2.4 / F2.5)

```python
dbc.Modal(
    [
        dbc.ModalHeader("In-flight dataset migration"),
        dbc.ModalBody(
            [
                dbc.Alert(
                    "Warning: in-flight dataset migration will potentially "
                    "alter Network Architecture and will permanently affect "
                    "History, Snapshots, and Training Replay.",
                    color="warning",
                ),
                html.P("Choose how to proceed:"),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button("Return to Stop & Restart",
                           id="live-switch-fallback-button",
                           color="secondary", outline=True),
                dbc.Button("Accept and proceed with live switch",
                           id="live-switch-accept-button",
                           color="warning"),
            ]
        ),
    ],
    id="live-switch-modal",
    is_open=False,
    backdrop="static",   # force an explicit choice (F2.4)
    keyboard=False,
)
```

* "Return to Stop & Restart" closes the modal and routes the user to the Phase 1 cold-swap path (the pending-banner UI from parent §3.5.1 / §3.5.2).
  * This satisfies F2.5.
* "Accept and proceed" POSTs to `/api/live_dataset_swap` (which forwards to cascor's `/v1/training/dataset/live`).
  * Success flashes a toast naming the pre-swap snapshot id; failure shows the server error verbatim.

### 4.4 Replay UI annotations (F2.9)

The Training Replay tab gains a swap marker on the timeline at each `dataset_swap` event.
Hovering shows the before/after dataset config; clicking seeks to the pre-swap snapshot.
Implementation detail: the existing replay component renders the history event stream — add a renderer for the new `dataset_swap` event type.

---

## 5. Demo-mode parity

`src/demo_mode.py` must mirror:

* `swap_dataset_live(**cfg)` → regenerates the synthetic dataset and emits a fake history event.
* `get_experimental_functions()` / `set_experimental_functions()` toggle.

Without the mirror, every `JUNIPER_CANOPY_DEMO_MODE=1` Phase-2 test silently skips (cf. parent §7.3).

---

## 6. Tests

### 6.1 Cascor

| File                                                       | What it asserts                                                                                                                                  |
|------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `tests/integration/test_live_swap_basic.py`                | Start training, swap to a different generator, assert post-swap iteration uses new dataset                                                       |
| `tests/integration/test_live_swap_gated.py`                | With experimental disabled, the route returns 403 and training is unchanged                                                                      |
| `tests/integration/test_live_swap_not_running.py`          | When training isn't running, route returns 422                                                                                                   |
| `tests/integration/test_live_swap_history_event.py`        | After swap, training history contains a `dataset_swap` event with before/after cfg                                                               |
| `tests/integration/test_live_swap_snapshot_captured.py`    | Pre-swap snapshot exists and can be loaded via `snapshot_manager.load(snapshot_id)`                                                              |
| `tests/integration/test_live_swap_replay.py`               | Run a session with a swap, replay it, assert iteration N produces the same loss both times                                                       |
| `tests/integration/test_live_swap_grow_output.py`          | Swap from 2-class to 3-class — assert output layer expanded in place (zero-init), hidden preserved (P2-1c)                                       |
| `tests/integration/test_live_swap_shrink_input.py`         | Swap from 5-input to 3-input — assert prepended 3-node input adapter, original 5-input layer retained (P2-1d)                                    |
| `tests/integration/test_live_swap_shrink_sequential.py`    | 5-N-4 → 3-5-N-4-2 → 7-5-N-4-9 sequential composition matches §3.6 worked example (P2-1d)                                                         |
| `tests/integration/test_live_swap_abandons_candidates.py`  | Swap during candidate-training mode — assert pool is dropped, response includes abandoned_candidate_pool_size, restart enters output mode (§3.5) |
| `tests/integration/test_live_swap_swap_in_progress_409.py` | Concurrent swap requests get 409; flag clears in `finally` (§3.7 #3)                                                                             |
| `tests/integration/test_live_swap_pause_timeout_504.py`    | If pause boundary not reached in 10s, swap aborts with 504; training continues (§3.7 #2)                                                         |
| `tests/integration/test_live_swap_failure_restore.py`      | Inject juniper-data fetch failure → assert old tensors restored, training resumes on old dataset, 5xx response (§3.8)                            |
| `tests/integration/test_live_swap_dim_unsupported.py`      | P2-1a/1b: dim change → 422 `dim_change_unsupported`. P2-1c: shrink → 422 `shrink_unsupported`                                                    |
| `tests/integration/test_live_swap_cancel.py`               | DELETE during in-flight swap → swap aborts cleanly, training resumes on old dataset (P2-1b)                                                      |

### 6.2 Canopy

| File                                                    | What it asserts                                                                              |
|---------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `tests/ui/test_experimental_toggle_persists.py`         | Toggle on, reload page, toggle is still on (`persistence_type="local"` works)                |
| `tests/ui/test_live_switch_disabled_default.py`         | Without experimental on, the Live Dataset Switch button is `disabled`                        |
| `tests/ui/test_live_switch_disabled_when_idle.py`       | With experimental on but training not running, button is still disabled                      |
| `tests/ui/test_live_switch_modal_two_step.py`           | Click Live Dataset Switch → modal opens with backdrop=static, backdrop click does nothing    |
| `tests/ui/test_live_switch_fallback_to_cold.py`         | Modal → Return to Stop & Restart → modal closes, pending-dataset banner from Phase 1 visible |
| `tests/ui/test_live_switch_accept_posts.py`             | Modal → Accept → POST to `/api/live_dataset_swap` observed; toast shows snapshot id          |
| `tests/ui/test_replay_swap_marker.py`                   | Replay tab shows a marker at the swap timestamp; hover shows before/after cfg                |
| `tests/regression/test_server_gate_overrides_client.py` | If server reports `experimental: false`, client toggle reverts to off within one poll cycle  |

### 6.3 Cross-cutting

* `tests/regression/test_phase2_off_by_default.py` (also referenced from
  parent §3.7) — boots canopy + cascor with no env override, asserts the
  toggle is off, the button is disabled, and the modal cannot be opened.

---

## 7. Phase 2 PR series

P2-1 was split into four sub-PRs at the 2026-05-10 design review (Appendix A) once the architecture
adapter (§3.6) and lock-during-fetch concerns (§3.4) became clear. P2-1a is the smallest landable
unit; P2-1d was originally planned as the largest (the prepend-adapter approach below). The
2026-05-13 redesign (§3.6) reduced P2-1d's scope substantially — the design doc is now in
[`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md)
and the implementation shipped as cascor #252.

| PR | Repo | Scope | Depends on |
| :--- | :--- | :--- | :--- |
| P2-0 | canopy | This spec doc update — captures locked-in design decisions before any code lands | (none) |
| P2-PRE-1 | cascor | **Defect fix** (discovered by §3.4 pause-boundary audit): make `pause_training` and `stop_training` actually interrupt the training loop. Wires signal checks into `_output_training_callback` + `_grow_iteration_callback` via a `TrainingInterrupted` sentinel that `monitored_fit` catches | (none) |
| P2-1a | cascor | Experimental-functions gate + bare `swap_dataset_live` skeleton (pause → reload → restart fit in output-mode → resume); rejects any dim change with 422; demo mirror | P2-PRE-1 |
| P2-1b | cascor | Cancel mechanism (`DELETE /v1/training/dataset/live`) + structured log + auto-snap reset + topology rebroadcast plumbing (no-op for equal-dim) | P2-1a |
| P2-1c | cascor | Additive-only architecture adapter (grow input/output via in-place expansion, zero-init); rejects shrink with 422 | P2-1b |
| P2-1d | cascor | **Redesigned 2026-05-13.** Shrink + grow via the network's `_resize_network_for_dataset` (monotonic-growth, random-init new connections) + lifecycle `_pad_dataset_for_network` (zero-pad dataset up to network capacity) + loss masking on `active_output_dim`. Replaces the §3.6 prepend-adapter approach. Design doc: [`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md). | P2-1c |
| P2-2 | cascor | History persistence: `dataset_swap` event in `TrainingHistory` + serializer. Post-redesign the topology is structurally unchanged across swaps (no adapter chain to round-trip) — the event just records the dim deltas. | P2-1d |
| P2-3 | cascor | Pre- AND post-swap snapshots + Replay reconstruction handler (instantaneous transformation, per §8 Answer 3) | P2-2 |
| P2-4 | canopy | Experimental Functions toggle + persistent `dcc.Store` + admin-route plumbing | Parent PR-7 |
| P2-5 | canopy | "Live Dataset Switch" button (gated) + two-step warning modal + dataset-loading toast with progress + cancel button | P2-4, P2-1b |
| P2-6 | canopy | Wire Live Switch adapter to cascor `/v1/training/dataset/live` + UI tests (POST /api/state pattern per Playwright limitation memory) | P2-5, P2-1a |
| P2-7 | canopy | Replay UI swap markers + History paired-diff (per §8 Answer 2) + Snapshots view annotations | P2-3, P2-6 |

**Suggested ordering**:

1. `P2-0` first (this doc; docs-only).
2. `P2-PRE-1` next (defect fix; benefits every user, not just Phase 2). Stand-alone bug fix.
3. `P2-1a → P2-1b` once P2-PRE-1 is merged — both small and reviewable, ship before any canopy work consumes the live endpoint.
4. `P2-1c` and `P2-4 → P2-5` can ship in parallel once `P2-1b` is in.
5. `P2-1d` was originally planned as the architectural change requiring its own design doc.
   The 2026-05-13 redesign collapsed that scope significantly — the design doc still exists at
   [`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md),
   but it documents a much smaller surface (in-place tensor resize + dataset pad) than the
   original §3.6 adapter chain would have required.
6. `P2-2 → P2-3` follow once `P2-1d` is settled. Post-redesign the cascade topology is
   structurally unchanged across swaps, so the snapshot serializer + replay reconstructor
   inherit no new layer types.
7. `P2-6` converges the cascor + canopy branches.
8. `P2-7` lands last and consumes everything before it.

---

## 8. Open questions for Phase 2 — RESOLVED 2026-05-10

All four open questions were resolved in the 2026-05-10 design review (Appendix A). Recorded
verbatim below; consumed by §3, §4, §5 and §7 of this document.

1. **RESOLVED 2026-05-10** — Should the experimental-functions toggle persist *per user* (via
   `dcc.Store(persistence_type="local")`) or *globally on the server* (env var only)?
   * **Answer**: Both — local UX persistence + server gate that authoritatively overrides
     the client (F2.10). See §3.1, §4.1.

2. **RESOLVED 2026-05-10** — When a swap triggers an architecture change, should the Snapshots
   tab show the pre- and post-swap snapshots as a paired diff, or as two independent entries?
   * **Answer**: Pre-swap snapshot, paired diff, AND post-swap snapshot (all three). See §3.9, P2-3, P2-7.

3. **RESOLVED 2026-05-10** — For Replay: do we play back the architecture change as an
   instantaneous transformation, or do we animate it?
   * **Answer**: Instantaneous transformation. See §3.9.

4. **RESOLVED 2026-05-10** — Should the warning copy from §3.4.2 be the final wording, or
   should it go through a UX copy review?
   * **Answer**: Ship verbatim, mark for post-launch UX review. See §4.3.

    **New open question** (introduced by 2026-05-10 design review, not yet resolved):

5. **OPEN** — How exactly does `_run_training` accept the `mode="output_training_first"` flag
   from §3.2 step 14? Two candidates: (a) a new kwarg threaded through `_run_training` →
   `network.fit()` that forces an entry-state of "output training, fresh epoch on the new
   dataset"; (b) a state mutation on `self` (e.g. `self._next_fit_mode_override`) that
   `_run_training` reads and clears at start. Option (b) is smaller-blast-radius (no fit()
   signature change) but introduces a hidden side-channel. Resolve before P2-1a code lands.

---

## 9. Validation / self-review checklist

* [x] Each functional requirement (F2.1–F2.10) is traced to at least one cascor or canopy implementation point above.
* [x] Server-side gate (F2.10) is independent of the client toggle.
* [x] Fallback path (F2.5) routes back to Phase 1 cold-swap, not a dead end.
* [x] History / Snapshots / Replay each have a dedicated PR (P2-2 / P2-3) so no requirement is silently bundled.
* [x] Demo-mode parity (parent §7.3) addressed in §5.
* [x] Tests are split between fix-verification (cascor §6.1, canopy §6.2) and regression (§6.3).
* [x] PR series has explicit dependency edges and converges before the Replay UI lands.
* [x] Open questions are non-blocking for Phase 1.

## Appendix A

Live datatset switch design discussion and open questions

Option C (abandon all candidates, immediately transfer to output training) — strongest.

* Matches your own reasoning: candidates trained against the old residual error are correlating against a signal that no longer exists. Promoting them risks negative transfer.
* Deterministic, simplest, smallest blast radius.
* Loses some compute, but candidate-pool training is by design ephemeral — pools are routinely abandoned when a cascade unit is added. One extra pool discard is within the normal lifecycle.

Option B (add already-correlated candidates, abandon rest) — theoretically appealing, practically risky.

* "Correlated against the old error signal" doesn't mean "useful for the new task." Adding such a unit locks in a feature that may actively mislead on the new dataset, and once a unit is in the cascade it's frozen — you can't take it back out.
* Selection criterion gets ambiguous: do you use the cached old-residual correlation? Recompute against the new residual (which doesn't exist yet because you haven't run the inference epoch)? Either choice is hard to defend.

Option A (finish candidate training, then swap) — violates the spirit of "live."

* Spends compute on a training step the user has already decided is irrelevant. A user clicks "Live Switch" because they want it now; making them wait for a candidate phase to finish defeats the responsiveness goal.

Recommendation: Option C. As a small softening, surface {"abandoned_candidate_pool_size": N} in the swap response so the UI can show "Swap discarded 8 in-flight candidates" — observability without semantic compromise.

Strengths of the overall approach

1. Preserves accumulated learning. Keeping hidden nodes intact means the cascade's feature hierarchy survives. Big win when datasets are related.
2. Mode-aware. Recognizes the asymmetry between output training (safely interruptible — simple gradient descent on output weights) and candidate training (error signal is the target, and that target is now stale).
3. Forces canonical post-swap state. Restarting in output-training mode on the new dataset means the network always reaches a consistent state before any candidate work resumes.
4. Avoids fit() inner-loop refactor. Transition orchestrated externally via pause + tensor swap + state machine, not by re-reading self._train_x mid-iteration. Keeps the cascade_correlation.fit contract intact — much lower regression risk than the rejected option-3.

Weaknesses & risks

1. Pause-boundary semantics are unclear. _pause_event is checked somewhere inside fit(). Need to verify it's at a clean boundary (epoch end, not mid-batch). Pausing mid-batch with partial gradient applied leaves an inconsistent network for the architecture modify step. This needs to be confirmed before implementation; if the boundary is too coarse (e.g., between cascade iterations), pause latency could be many seconds.
  **Response**:
    * Pause boundary semantics are important but are expected to already exist in a sensible, functional form.
    * The training pause function was implemented substantially earlier in the deveopment process.
    * Investigating this issue is critical, but if a gap is identified, it should be documented as a newly discovered defect in previously completed code and treated like the high priority bug fix that it is.
    * Ultimately, this functionality is a requirement and any latent, problematic implementations will be likely to surface as the canopy web frontend becomes more responsive over time.
    * So IMHO, totally worth the squeeze.

2. "Modify architecture appropriately" hides real complexity.
    * Adding input nodes: new connections fan into every existing hidden node. What initialization? Zero (reproducible, no immediate effect, slow to learn) vs. small-random (matches existing init scheme, but causes immediate accuracy disturbance). I'd default to zero — it's the only choice that guarantees the post-swap network's output on the overlapping input subset is unchanged.
    * Removing input nodes: drop the full column of weights from input→hidden. Information loss, but inevitable.
    * Adding output nodes: new output weights need init. Same zero-vs-random tradeoff. Zero is again defensible: the new output simply has no opinion until training begins.
    * Removing output nodes: trained output weights for that class are gone. Irrecoverable. The user should probably get a confirmation prompt at the UI layer when output_dim shrinks.
  **Response**:
    * For additive changes, the existing design makes sense--keep the existing nodes, add 1 or more as needed. There is no meaningful data loss.
    * As you point out, however, migrating to a dataset with smaller geometry than the current dataset results in permanent data loss.
    * This violates the spirit of the live dataset switch requirement.
    * The fundamental desire here is to add new functionality with new dataset training without meaningful loss of existing function.
    * For datasets with smaller geomentry than the current dataset, add a new layer (input/output/both) for the new dataset's smaller dimension(s).
    * So, e.g., for dataset 1 with ip/op geometry of 5/4 and a live migration to dataset 2 with ip/op geometry of 3/2, the original cascor network with 5-N-4 input, hidden, output topology would transition to a new topology of 3-5-N-4-2 new input, old input, hidden, old output, new output.
    * This *should* allow for old learning to be retained at some level.

3. Semantic vs. geometric change is invisible. Spirals → moons (both 2D, 2-class) wouldn't trigger any architecture change but the distribution is fundamentally different. Output retraining alone may not adapt the hidden features well — negative transfer risk. Not a blocker (the user opted in by clicking the switch) but worth a known-limitation note.
  **Response**:
    * Very true, but in the spirit of the experimental, research-based nature of the project, i think.

4. Auto-snap ratchet pollution. _auto_snap_best_metric is a running best across epochs. After a swap, the metric scale changes — what was "best on spirals" is meaningless on moons. Without resetting, the post-swap training may never beat the stale ratchet and auto-snap stops firing entirely. Must clear _auto_snap_best_metric at swap time, mirroring the fresh-start logic at manager.py:1898-1900.
  **Response**:
    * Agreed, the ratchet mechanism is meaningless if it doesn't reflect the network performance for the current dataset.

5. Topology rebroadcast. When input or output layer cardinality changes, the canopy topology view goes stale. Need a full topology broadcast on swap completion. (You already shipped the fix for cascade_add count-only-stub broadcast in #238 — same surface.)
  **Response**:
    * Agreed, anytime there is a live dataset switch, topology needs to be re-broadcast.

6. State machine has no "swapping" phase. Right now FSM modes are Started/Paused/Stopped/etc. Concurrent commands during a swap (user clicks Resume or Stop mid-swap) need defined behavior. Either:
    * Add a transient Swapping state that rejects user commands until done, OR
    * Hold the lock + a soft _swap_in_progress flag and return 409 Conflict on competing commands.
  I'd go with the flag approach — cheaper than an FSM change.
  **Response**:
    * Yeah, i think i agree with the flag approach.  As far as the FSM knows, the network is just in a paused state.  It sounds reasonable to put the burden of rejecting user commands on the dataset switch code.

7. juniper-data fetch latency holds _training_lock. The fetch is network I/O (could be 5–30s for large datasets). If get_status paths take the same lock, the canopy status panel freezes during swap. Need to verify and possibly drop the lock around the I/O step (with the swap-in-progress flag protecting reentry).
  **Response**:
    * Good point. This needs to be investigated. This should also inform user feedback during the data load.
    * The loading new dataset toast should have the focus--to minimize the need for get_status calls for dashboard updates--and should have a live progress indicator of some sort.
    * This dataset loading toast would also be a good place to have the cancel option.

8. Failure must restore old dataset cleanly. If juniper-data is unreachable, or the architecture modify raises, the swap should:
    * Restore the old _train_x/_train_y refs (snapshot before mutating).
    * Resume training on the old dataset.
    * Return a clear 5xx error.
    * Never leave training paused-forever or with a half-swapped architecture.
  **Response**:
    * I agree; this is an absolutely critical requirement.

9. fit() doesn't currently support "restart from output training mode after pause". The training thread captured the original tensors at submit time (manager.py:1928). After the swap, those refs are stale. Even if we mutate self._train_x, the running
fit() closure won't see it. So Option C-with-Option-1's mechanism: we still need to stop the training future, then submit a new one with the new tensors and a flag forcing output-mode entry. The "fit() inner loop isn't involved" is true at the
code-modification level (no changes to fit()), but at the runtime level we are restarting fit() — the old future ends, a new one begins, with continuity provided by the preserved network state (weights + cascade structure), not by the future itself.
  **Response**:
    * That's fair. It does look like we need to load a new tensor with a flag that forces output training mode.
    * We definitely want to start the new dataset processing by launching output training rather than immediately generating a new error signal.
    * This approach mirrors the overall cascor strategy of training output first, then generating error signal, then training candidates.
    * And, arguably, any cpu cycles spent calculating the untrained error signal and training candidates on it will, from a practical standpoint, be completely wasted.

10. This is a meaningful semantic to be precise about: "fit() restart with preserved network", not "fit() pause-and-continue". Worth being explicit in docs/log messages so a future debugger isn't misled.
  **Response**:
    * For live dataset migrations, the semantic should be pause, update architecture, continue with new iteration of output training.
    * This assumes the recommended option to abandon candidate nodes during live dataset switch.
    * This also asumes that the functionality called for in items 6 and 9 above has been developed.

Guardrails I'd add

1. Pre-swap snapshot of mutable state: copy refs to _train_x/_y/_val_x/_val_y and the network's structural state before any mutation, so failure can revert.
2. Hard timeout on pause: if the training thread doesn't reach the pause boundary within ~10s, abort the swap (504), don't block forever.
3. Idempotency / concurrent-swap guard: _swap_in_progress flag → 409 Conflict on competing requests.
4. Dimension sanity check: reject swap if new input_dim or output_dim is 0/negative or absurdly large (configurable cap).
5. Structured log line: "swap: input 2→3, output 2→2, hidden 5 preserved, candidates 8 abandoned, mode→output_training" — critical for post-mortem.
6. Reset _auto_snap_best_metric as part of the swap.
7. Always force topology rebroadcast on swap completion.
8. Return shape: {status, before_cfg, after_cfg, arch_changes: {input_delta, output_delta, hidden_preserved, abandoned_candidates}, mode: "output_training"} — gives canopy enough to populate the timeline marker without a follow-up GET.

**Response**: These guardrails look good.

Scope implication for P2-1

This significantly enlarges P2-1 beyond the original spec ("no persistence yet, gate enforced"). The architecture-modify logic alone is non-trivial and probably belongs to its own helper (call it architecture_adapter.adapt_for_dataset_swap(network,
before_dim, after_dim)) with its own tests. I'd suggest splitting:

* P2-1a: gate (set/get_experimental_functions + admin routes) + bare swap_dataset_live skeleton that pauses + restarts fit on the new dataset, no arch change support yet (reject swaps that change input/output dim with 422).
* P2-1b: architecture adapter (input/output node add/remove, hidden preservation) + unblocks dim-changing swaps.
* P2-2: history persistence (dataset_swap event).
* P2-3: snapshots + replay.

P2-1a is small enough to land safely in a day; P2-1b carries the real risk and deserves its own review.

---

Open question for you: split P2-1 into 1a/1b as above, or keep it monolithic? And do you want Option C (abandon candidates) confirmed for the candidate-pool policy, or is one of the others worth more discussion?

**Response**: Yeah, let's split P2-1 as described.  The I agree that the abandon candidates approach is the best option.

---

## Appendix B — §3.6 prepend-adapter design (RETIRED 2026-05-13)

The text below is the **original** §3.6 architecture-adapter pattern as locked-in at the
2026-05-10 design review. It is **retired and not implemented**. Preserved verbatim here as
historical record of how the design evolved; do not consult it for current implementation
guidance. The replacement design lives in §3.6 above and is fully specified in
[`juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md`](../../juniper-cascor/notes/PHASE_2_P2_1D_DESIGN_2026-05-13.md).

The retirement happened mid-P2-1d implementation: P2-1c (cascor #251) had shipped the grow
side with zero-init connections. When P2-1d kicked off, two tensions in this §3.6 design
surfaced during the design check-in and could not be resolved without further deviation from
Paul's long-term modelling goals:

1. **Zero-init signal-flow collapse on shrink.** With a pure-linear input adapter `Linear(I_new→I_old)`
   zero-init, the original network sees zero input. Hidden activations collapse to bias-only
   constants. The output adapter (also zero-init) maps those constants to literal zeros for
   every prediction. Day 1 after a shrink the model produces zero across the board until
   retraining catches up — qualitatively different from P2-1c's zero-init invariant where
   the forward pass was *preserved* exactly on the still-present input subset.

2. **Grow-after-shrink semantics required rewriting P2-1c.** Once an adapter is prepended,
   the "outermost layer" is the adapter, not the network. P2-1c's grow code mutated
   `network.input_size` directly; grow-after-shrink with that code would silently corrupt
   the network. The fix would have required threading "is there an adapter? grow that
   instead" into every dim-management path.

The 2026-05-13 redesign (current §3.6) avoids both issues by never shrinking the network at
all. Dataset shrink becomes dataset zero-padding; the cascade topology stays structurally
unchanged across every swap. The original adapter design's intended preservation of
structural memory is achieved trivially (the network was never modified) without the
adapter-layer apparatus.

### Original §3.6 text (verbatim, retired)

> When the new dataset's input or output dimension differs from the current network, the
> architecture adapter modifies only the boundary (input and output) layers. **All hidden nodes
> and inter-hidden cascade connections are preserved unchanged.**
>
> **Sequential composition rule** (chosen 2026-05-10):
>
> * **Grow** — expand the current outermost input and/or output layer **in place** to the new
>   dimension. New connections are zero-initialized (preserves overlapping-input behavior; the
>   post-swap network's output on the still-present input subset is unchanged at swap-time).
>   No new layers are created.
> * **Shrink** — **prepend** a new input-side adapter layer at the new (smaller) input dim, and
>   **append** a new output-side adapter layer at the new (smaller) output dim. Connections from
>   the new adapter into the next layer are zero-initialized. The original layers are retained;
>   the network monotonically deepens by one input-adapter + one output-adapter on each shrink swap.
> * **Mixed** — apply each side independently per its own delta (e.g. input grows + output shrinks).
>
> The outermost input/output layers are **always** the live-dataset boundary, regardless of how
> many adapter layers have accumulated.
>
> **Worked example** (sequential swaps, starting topology `5-N-4`):
>
> | Step | Operation                | Topology after          | Notes                                                                        |
> |------|--------------------------|-------------------------|------------------------------------------------------------------------------|
> | 0    | initial                  | `5-N-4`                 | hidden = N cascade-grown units                                               |
> | 1    | shrink to (3 in / 2 out) | `3-5-N-4-2`             | prepend 3-input adapter; append 2-output adapter                             |
> | 2    | grow to (7 in / 9 out)   | `7-5-N-4-9`             | expand outermost input adapter 3→7; expand outermost output adapter 2→9      |
> | 3    | shrink to (1 in / 1 out) | `1-7-5-N-4-9-1`         | prepend new 1-input adapter; append new 1-output adapter                     |
> | 4    | grow to (4 in / 6 out)   | `4-7-5-N-4-9-6`         | expand outermost input adapter 1→4; expand outermost output adapter 1→6      |
>
> This rule is implemented in `architecture_adapter.adapt_for_dataset_swap`. The full layered
> topology must be captured in snapshots and reconstructed on replay (§3.4 history/snapshots).
