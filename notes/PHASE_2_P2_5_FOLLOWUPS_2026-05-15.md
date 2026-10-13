# P2-5 follow-ups: active "Stop & Restart" UX polish

**Status**: Captured 2026-05-15 during P2-5 design discussion. Not yet scheduled.
**Parent PR**: P2-5 (`phase2/p2-5-live-dataset-switch`).

P2-5 ships the **minimal** interpretation of the "Return to Stop & Restart" modal-cancel button per spec §4.3:

> Click "Return to Stop & Restart" → modal closes. The Apply Dataset button is right beside the (now-closed) Live Dataset Switch button — same form, same sidebar inputs, no extra friction for the user to use the cold-swap path.

Three "active" interpretations were considered during P2-5 scoping and deferred. Each could be picked up independently as a small UX-polish PR if the minimal interpretation turns out to be confusing in practice. None block any downstream Phase 2 work.

---

## Follow-up A — auto-scroll to Apply Dataset button

### What

When the user clicks "Return to Stop & Restart", in addition to closing the modal, scroll the sidebar so the Apply Dataset button is in view. Useful if the user has scrolled past the NN section while the modal was open.

### Why deferred

The current sidebar isn't long enough on a typical viewport that "scroll to Apply Dataset" is meaningful — the Apply Dataset button is usually already visible. If user reports start showing "I couldn't find the cold-swap path after cancelling the live switch", revisit.

### Sketch

Clientside callback in `dashboard_manager.py`:

```python
self.app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        const btn = document.getElementById('apply-dataset-button');
        if (btn) btn.scrollIntoView({behavior: 'smooth', block: 'center'});
        return window.dash_clientside.no_update;
    }
    """,
    Output("apply-dataset-button", "id"),  # no-op output
    Input("live-switch-fallback-button", "n_clicks"),
    prevent_initial_call=True,
)
```

### Effort

~20 LOC. Trivial.

---

## Follow-up B — pulse / highlight Apply Dataset button briefly

### What

After scrolling (or simultaneously), apply a brief CSS animation to the Apply Dataset button so it visually attracts attention for ~1 second. Common UX pattern for "look here next".

### Why deferred

Adds CSS scaffolding (a new `@keyframes` rule + a transient className) plus a callback to apply/remove the className. If Follow-up A lands first, the visual cue may be sufficient on its own; if not, pulse is the next escalation.

### Sketch

- New CSS class `.attention-pulse` in `assets/dashboard.css` with a 1s keyframe animation.
- Callback that adds the class on `live-switch-fallback-button.n_clicks` and removes it via a delayed clientside callback (or `setTimeout`).

### Effort

~50 LOC including CSS + callback + test that the className is applied.

---

## Follow-up C — pre-populate the Phase 1 pending-dataset-banner

### What

When the user clicks "Return to Stop & Restart", in addition to closing the modal, call `/api/stage_dataset` with the same dataset config the user had selected in the sidebar. This puts the Phase 1 cold-swap into "staged" state so when the user clicks Apply Dataset (or restart-training), the cold swap happens immediately with the config they'd already chosen.

The pending-dataset-banner from §3.5.1 / §3.5.2 then becomes the visible affordance: "You have a pending dataset change. Apply Dataset or Cancel."

### Why deferred

Highest-effort of the three. Implies the modal-cancel button does work (stages the dataset) — different semantics from "Return to Stop & Restart" (the user has explicitly chosen NOT to swap right now). Could confuse: the user clicks cancel and finds the system has done something anyway. The minimal interpretation preserves "Cancel = nothing happens; you decide what to do next" which is clearer.

If user feedback says "I clicked Cancel and then forgot to apply the cold-swap, my dataset wasn't updated", this becomes worth doing.

### Sketch

- Reuse the existing `/api/stage_dataset` POST from Phase 1.
- Modal-cancel callback fires the POST with the sidebar State values.
- The existing pending-dataset-banner appears on success.

### Effort

~80 LOC plus tests. Largest of the three.

---

## Pickup order

If any are needed, suggested order:

1. **Follow-up A (scroll)** first — smallest, least UX-controversial.
2. **Follow-up B (pulse)** if A's scroll alone doesn't surface the button enough.
3. **Follow-up C (pre-stage)** only if explicit user feedback points at the "I clicked Cancel and now I don't know what to do" failure mode.

All three can stay deferred indefinitely without blocking anything.
