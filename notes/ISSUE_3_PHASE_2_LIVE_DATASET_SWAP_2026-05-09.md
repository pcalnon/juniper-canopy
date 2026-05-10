# Issue #3 Phase 2 — Live Dataset Switch (2026-05-09)

* **Author**: Paul Calnon (drafted by Claude Code Opus 4.7)
* **Status**: Draft for review — derived from §3.4.2 of `FRONTEND_ISSUES_PLAN_2026-05-09.md`
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

### 3.2 Live-swap lifecycle method

```diff
--- a/src/api/lifecycle/manager.py
+++ b/src/api/lifecycle/manager.py
@@ class CascorLifecycleManager
+def swap_dataset_live(self, **cfg) -> Dict[str, Any]:
+    """In-flight dataset swap. Pauses, snapshots, swaps, records, resumes.
+
+    Requires experimental-functions to be enabled server-side. Returns 422
+    when training is not currently running, 403 when the gate is closed.
+    """
+    if not self._experimental_functions_enabled:
+        raise PermissionError("experimental_functions_disabled")
+    if not self.is_training_running():
+        raise ValueError("training_not_running — use POST /v1/training/dataset (cold swap) instead")
+
+    # 1. Pause the training thread at the next iteration boundary.
+    self._pause_event.clear()
+    self._wait_until_paused(timeout_s=10.0)  # raises on timeout
+
+    # 2. Snapshot pre-swap state. Snapshot id is returned to the caller so
+    #    Replay can rewind to this point.
+    pre_swap_snapshot_id = self.snapshot_manager.capture(reason="pre_dataset_swap")
+
+    # 3. Reload dataset. _reload_dataset is the same helper used by the
+    #    cold-swap path so behavior stays consistent.
+    before_cfg = self._dataset_config_snapshot()
+    self._reload_dataset(**cfg)
+    after_cfg = self._dataset_config_snapshot()
+
+    # 4. If the new dataset's input/output shape differs, the network may
+    #    need an output-head reset and candidate-pool flush. Delegate to
+    #    the architecture manager (existing component).
+    arch_changes = self.architecture_manager.adapt_to_dataset(
+        before=before_cfg, after=after_cfg
+    )
+
+    # 5. Record the swap as a first-class history event (F2.7).
+    self.training_history.record_event(
+        event_type="dataset_swap",
+        timestamp=time.time(),
+        payload={
+            "before": before_cfg,
+            "after": after_cfg,
+            "pre_swap_snapshot_id": pre_swap_snapshot_id,
+            "arch_changes": arch_changes,
+        },
+    )
+
+    # 6. Publish to the status WebSocket so canopy can mark the timeline.
+    self.status_publisher.publish({
+        "type": "dataset_swap",
+        "timestamp": time.time(),
+        "before": before_cfg, "after": after_cfg,
+        "arch_changes": arch_changes,
+    })
+
+    # 7. Resume.
+    self._pause_event.set()
+    return {
+        "status": "swapped",
+        "pre_swap_snapshot_id": pre_swap_snapshot_id,
+        "arch_changes": arch_changes,
+    }
```

`_dataset_config_snapshot()` returns the current `dataset_type`, `n_samples`, `noise`, `rotations`, `n_spirals`, etc. — whichever set is meaningful for the active generator.

`architecture_manager.adapt_to_dataset(before, after)` is a new helper.
For the spirals-only case it can be a no-op returning `{}`.
For cross-generator swaps it may reset the output head when the class count changes and flush the candidate pool when the input dimensionality changes.
Specifics are an implementation detail per §3.4.2.

### 3.3 REST surface

```diff
--- a/src/api/routes/training.py
+++ b/src/api/routes/training.py
@@
+@router.post("/v1/training/dataset/live")
+async def swap_dataset_live(
+    cfg: DatasetSwapRequest,
+    manager: LifecycleManager = Depends(get_manager),
+):
+    try:
+        return manager.swap_dataset_live(**cfg.dict(exclude_none=True))
+    except PermissionError as e:
+        raise HTTPException(status_code=403, detail=str(e))
+    except ValueError as e:
+        raise HTTPException(status_code=422, detail=str(e))
+
+@router.get("/v1/admin/experimental_functions")
+async def get_experimental_functions(manager: LifecycleManager = Depends(get_manager)):
+    return {"enabled": manager.get_experimental_functions()}
+
+@router.post("/v1/admin/experimental_functions")
+async def set_experimental_functions(
+    body: ExperimentalFunctionsToggleRequest,
+    manager: LifecycleManager = Depends(get_manager),
+):
+    return manager.set_experimental_functions(body.enabled)
```

The admin route is access-controlled separately (existing `JUNIPER_DATA_API_KEY` mechanism or equivalent).
Setting it from the canopy UI is **also** behind the client-side experimental toggle, so the user-facing path is two-gated by construction.

### 3.4 History / Snapshots / Replay (F2.7 / F2.8 / F2.9)

* **History**: `training_history.record_event(event_type="dataset_swap", ...)` needs a new `event_type` value plus a payload schema entry.
  * The history serializer (JSON / Cassandra row, depending on backend) must round-trip the payload unchanged.
* **Snapshots**: `snapshot_manager.capture(reason="pre_dataset_swap")` is the same path used elsewhere; the only Phase-2 work is to plumb the returned `snapshot_id` into the history event so replay can find it.
* **Replay**: the replay engine iterates history events. Add a handler for `dataset_swap` that:
  1. Loads the `pre_swap_snapshot_id` snapshot.
  2. Plays forward to the swap timestamp.
  3. Applies the same `_reload_dataset(**after)` + `architecture_manager.adapt_to_dataset(...)` calls.
  4. Continues replay from the post-swap state.
  * This makes playback reproducible across swaps.

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

| File                                                    | What it asserts                                                                            |
|---------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `tests/integration/test_live_swap_basic.py`             | Start training, swap to a different generator, assert post-swap iteration uses new dataset |
| `tests/integration/test_live_swap_gated.py`             | With experimental disabled, the route returns 403 and training is unchanged                |
| `tests/integration/test_live_swap_not_running.py`       | When training isn't running, route returns 422                                             |
| `tests/integration/test_live_swap_history_event.py`     | After swap, training history contains a `dataset_swap` event with before/after cfg         |
| `tests/integration/test_live_swap_snapshot_captured.py` | Pre-swap snapshot exists and can be loaded via `snapshot_manager.load(snapshot_id)`        |
| `tests/integration/test_live_swap_replay.py`            | Run a session with a swap, replay it, assert iteration N produces the same loss both times |
| `tests/integration/test_live_swap_arch_change.py`       | Swap from spirals (2-class) to a 3-class dataset, assert output head is reset accordingly  |

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

| PR   | Repo   | Scope                                                                                         | Depends on  |
|------|--------|-----------------------------------------------------------------------------------------------|-------------|
| P2-1 | cascor | `swap_dataset_live()` + `POST /v1/training/dataset/live` (no persistence yet, gate enforced)  | Parent PR-6 |
| P2-2 | cascor | History persistence: `dataset_swap` event in `TrainingHistory` + serializer                   | P2-1        |
| P2-3 | cascor | Snapshot at swap point + Replay reconstruction handler                                        | P2-2        |
| P2-4 | canopy | Experimental Functions toggle + persistent `dcc.Store` + admin-route plumbing                 | Parent PR-7 |
| P2-5 | canopy | "Live Dataset Switch" button (gated) + two-step warning modal                                 | P2-4        |
| P2-6 | canopy | `cancel_pending_dataset` Phase-1 already shipped; here we wire Live Switch adapter + UI tests | P2-5, P2-1  |
| P2-7 | canopy | Replay UI swap markers + History / Snapshots view annotations                                 | P2-3, P2-6  |

Suggested ordering: `P2-1 → P2-2 → P2-3` ship in parallel with `P2-4 → P2-5`; both branches converge at `P2-6`; `P2-7` lands last.

---

## 8. Open questions for Phase 2

These are questions to resolve before P2-5 (UI) lands. None block Phase 1.

1. Should the experimental-functions toggle persist *per user* (current plan, via `dcc.Store(persistence_type="local")`) or *globally on the server* (env var only)? Current plan: both — local UX persistence + server gate that authoritatively overrides the client.
2. When a swap triggers an architecture change, should the Snapshots tab show the pre- and post-swap snapshots as a paired diff, or as two independent entries?
3. For Replay: do we play back the architecture change as an instantaneous transformation, or do we animate it (the latter is much more work)?
4. Should the warning copy from §3.4.2 ("Warning, in-flight dataset migration will potentially alter Network Architecture and will permanently affect History, Snapshots, and Training Replay.") be the final wording, or should it go through a UX copy review? Current plan: ship verbatim, mark for follow-up review post-launch.

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
