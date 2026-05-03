# Replay V2 — Canopy User-Facing FAQ

**Created**: 2026-05-03
**Status**: Active (V2 ships via CAN-015g g-1..g-6 cascor + g-4 canopy)
**Project**: Juniper Canopy
**Tracks**: CAN-015g (Replay V2 — per-epoch weight history)

---

## What this doc covers

The canopy-side companion to
[`juniper-cascor/notes/development/SNAPSHOT_SCHEMA_V2.md`](https://github.com/pcalnon/juniper-cascor/blob/main/notes/development/SNAPSHOT_SCHEMA_V2.md).
Same target audience (reviewers + ops + curious users), but
canopy-side concerns: what the player UI does with V2 snapshots,
what the indicator badges mean, why the buffer is capped, and
why decision-boundary playback "lags" the metric scrubber.

For implementation roadmap and design rationale see the parent plan
at
[`juniper-ml/notes/PHASE_6E_DEFERRED_CAN-015GH_DESIGN.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/PHASE_6E_DEFERRED_CAN-015GH_DESIGN.md).

---

## What changed in the player UI

The Replay tab is unchanged structurally from B-6 (Phase 6E Sprint
B). Three additions in CAN-015g g-4:

1. **`V2 ✓ weights` / `V1 (metrics only)` badge** next to the FSM
   state badge. Driven by the snapshot's `weights_available`
   field. V2 means the snapshot was produced by a training run
   with weight-history capture enabled (cascor g-6 active); V1
   means the snapshot is metric-curve-only.
2. **`last sample: epoch N (M buffered)` readout** — shows the
   epoch of the most recently received weight sample and how many
   are currently buffered in the browser.
3. **`replay-weight-buffer` Store + clientside drain Interval** —
   browser-side ring buffer that holds the most recent weight
   payloads so scrubber moves within the buffer window are local
   (no cascor round-trip per scrub).

Two non-changes worth calling out:

- **Decision-boundary playback rendering** is **not yet wired** to
  the buffer. g-4 V1 ships the infrastructure; the actual rendering
  refactor (decision_boundary.py + network_evolution.py)
  is deferred to a follow-on PR. The badge tells you a snapshot is
  V2; the boundary view still shows the snapshot's terminal-epoch
  state during replay until that follow-on lands.
- **Scrubber position** still moves freely through the metric
  timeline. Only weight-dependent renders snap to sample boundaries.

---

## Indicator FAQ

### Q: What does the `V2 ✓ weights` badge actually mean?

The cascor backend received weight tensors from the loaded snapshot
and reports `weights_available=true` in the `/v1/snapshots/{id}/replay`
response. Once decision-boundary playback rendering ships, this is
the signal that the rendering will follow the scrubber. Until then,
the badge is informational only — it confirms the snapshot was
produced by a g-6-instrumented training run.

### Q: Why does my snapshot show `V1 (metrics only)` even though I'm running latest cascor?

Three possibilities, in decreasing order of likelihood:

1. **The snapshot was created by a training run that pre-dated
   g-6.** V2 capture only runs when the lifecycle's
   `_WeightHistoryRecorder` is attached, which happens via
   `start_training` after g-6 lands. Snapshots from earlier
   training runs are V1 forever — they were never captured.
2. **The training run had `weight_history_sampling_interval` set
   too sparse for the run's length.** A 30-epoch run with the
   default `N=50` produces zero periodic samples (no epoch is a
   multiple of 50). The terminal-capture path catches this —
   you should still see at least one sample (the final one).
   If `num_samples == 0`, `weights_available` is false even though
   the layout exists.
3. **The schema version on disk is unrecognized.** A future V3
   format that this canopy doesn't know about would degrade to
   V1 behaviour gracefully. Check the cascor logs for the warning
   line `weight_history schema_version: <N> (expected 2)`.

### Q: What is the `(M buffered)` count?

Number of weight payloads currently held in the browser's
`replay-weight-buffer` Store. Bounded by `REPLAY_WEIGHT_BUFFER_MAX`
(currently 100; see the inline comment in
`replay_player_panel.py`). Older payloads are LRU-evicted when the
ring fills up, so the count tells you how far back you can scrub
without a re-fetch.

### Q: The buffered count went from 12 down to 1. What happened?

A `stop` action on the replay session clears the buffer. Same with
loading a new snapshot via Restore/Replay — the Store resets so
stale tensors don't bleed across sessions.

### Q: Why is the cap 100 and not the 1000 the design plan suggested?

The plan's "1000 entries" target didn't account for tensor size.
A single weight payload for a production-sized network (say, 100
units × 100-input cascade order) is a few MB after base64
encoding. 1000 such entries × ~MB each = ~1 GB of browser memory
on the Replay tab alone. 100 entries gives a comfortable few
hundred MB ceiling. If your replays are short and tensors small,
you can raise the constant at the top of
`replay_player_panel.py`.

---

## "Snap to sample" UX FAQ

The cascor-side
[SNAPSHOT_SCHEMA_V2.md](https://github.com/pcalnon/juniper-cascor/blob/main/notes/development/SNAPSHOT_SCHEMA_V2.md)
covers the storage strategy that drives this behaviour. Summary
from the canopy perspective:

### Q: I scrubbed to epoch 137. The metric curves moved smoothly but the badge readout still says `last sample: epoch 100`. Why?

V2 captures weights only at sample-boundary epochs. With default
`N=50`, those are epochs 0, 50, 100, 150, … plus every cascade-grow
event. Epoch 137 isn't a sample boundary, so no fresh weight
payload arrived for it. The readout reflects the **most-recent
sample received**, not the scrubber position.

### Q: What's a "sample boundary" in the player?

An epoch at which the cascor lifecycle captured weight tensors. The
cascor `/v1/snapshots/{id}/replay` response includes a
`weight_sampling.sample_epochs` array listing them. The replay
session emits a `weights` block on its synthetic `epoch_end` event
only on these epochs.

### Q: Why doesn't the player interpolate between samples?

Linearly interpolating weight tensors between two epochs is
mathematically meaningless — the network at epoch 137 is **not** a
0.74 / 0.26 mix of epochs 100 and 150. The model's loss landscape
isn't linear in weight space at any nontrivial training scale. A
"smoothly interpolating" decision boundary view would mislead the
user into thinking they're seeing real intermediate states.

The deliberate behaviour is **snap to nearest sample**: the
weight-dependent renders show the most-recent sampled state. The
metric curves continue to move smoothly because they're captured
every epoch (not subsampled).

### Q: My playback feels "chunky" — can I get more samples?

Three options:

1. **Train with `weight_history_sampling_interval=1`** (every epoch).
   Effectively Option A from the parent plan. Snapshot file size
   grows ~50× over the default — fine for short experiments,
   prohibitive for production runs.
2. **Train with a smaller N** (say, 10 instead of 50). 5× more
   samples, 5× larger file. Linear tradeoff.
3. **Set `weight_history_max_samples` higher** (default 1000).
   Disables decimation kicks for longer runs. Watch the cascor
   process memory — each sample is held in-process during
   training.

All three are runtime-mutable via `PATCH /v1/training/params`
mid-run.

### Q: Will canopy ever interpolate weights for me?

Out of scope for V2. A V3 with delta encoding (Option B in the
parent plan) might enable cheaper near-exact reconstruction, but
that's a separate sprint and explicitly deferred until the snap-to-
sample UX is shown to be insufficient through user research.

---

## Performance characteristics

### Browser memory

- Steady state: `REPLAY_WEIGHT_BUFFER_MAX` × per-event size. With
  default 100 × ~MB-scale, expect a few hundred MB of weight data
  in the Store on a long replay session.
- During scrubber moves: no allocation (Store is read, no copy).
- During Stop / new Replay: buffer is cleared; old payloads are
  garbage-collected on next browser GC pass.

### CPU

- Drain Interval fires every **500 ms**. Each drain reads the JS
  ring buffer (small N, typically 0–4 events between fires), does
  a JSON serialize + Store write. Negligible CPU.
- Last-sample readout is pure clientside JS — no Python round-trip.
- The base64 decode happens **on demand** at render time (when
  decision-boundary playback rendering lands), not at receive time.
  Holding strings in the Store is cheap.

### Network

- WS frame size grows on sample-boundary epochs only. With default
  `N=50`, 1 in 50 metric events carries a multi-KB-to-MB weight
  block. Average frame size is dominated by the metric-only
  events.
- No new HTTP round-trips. All weight data flows through the
  existing WS metrics channel.

---

## Verifying everything wired correctly

### From the player tab

1. Load a snapshot via the Snapshots tab → click Replay.
2. The Replay tab opens. Look for **`V2 ✓ weights`** badge next
   to the FSM state. If you see `V1 (metrics only)`, the snapshot
   doesn't have a usable weight history — see the indicator FAQ
   above for why.
3. Click Play. Watch the `last sample: epoch N (M buffered)`
   readout. With default `N=50`, you should see updates every
   50 metric events as playback advances.
4. The buffer count should rise to ~10–20 within a few seconds at
   normal speed.

### From the browser console

```javascript
// Inspect the JS-side ring buffer
window._juniperWsDrain._replayWeightBuffer.length;
// Drain it to see what's queued
window._juniperWsDrain.drainReplayWeights();
```

### From cascor backend

```bash
# Confirm cascor is emitting the V2-shape events
curl -s -X POST http://localhost:8200/v1/snapshots/<id>/replay \
  | jq '.data.weights_available, .data.weight_sampling'
```

If `weights_available` is `false` here, no amount of canopy
debugging will help — the underlying snapshot is V1.

---

## Glossary (canopy-specific)

| Term | Meaning |
|---|---|
| **Replay V2** | The post-CAN-015g protocol — adds per-sample weight payloads to the synthetic `epoch_end` events emitted during replay. |
| **`replay-weight-buffer` Store** | Browser-side LRU ring (capacity `REPLAY_WEIGHT_BUFFER_MAX`) of recent weight payloads. Drained from the JS ws_dash_bridge ring buffer every 500 ms. |
| **Sample-boundary event** | A synthetic `epoch_end` event that cascor emitted with `is_sample_boundary=true` and a `weights` block attached. The bridge splits the block into the dedicated buffer to keep the metrics ring light. |
| **Snap to sample** | The player's behaviour when the scrubber is between two sample boundaries — weight-dependent renders show the most-recent sampled state, not an interpolation. |
| **V2 ✓ weights badge** | UI signal that the loaded snapshot has weight history available. Driven by the session Store's `weights_available` field, which mirrors cascor's `state_summary` response. |

---

## Related work

- **g-1** (cascor #180): serializer — shipped the V2 file format.
- **g-2** (cascor #189 — retarget of #184): replay session weight
  cache + extended `state_summary` — defines `weights_available`
  and `weight_sampling`.
- **g-3** (cascor #190 — retarget of #187): synthetic-event
  emission — produces the `weights` blocks the canopy buffer
  consumes.
- **g-4** (canopy #220): WS bridge buffer + player-panel
  indicators — what this doc describes.
- **g-5a** (cascor #196): cascor-side schema doc — sibling of this
  file.
- **g-6** (cascor #191): training-loop weight capture — the
  write-side without which all of the above only works on ad-hoc
  test fixtures.
- **deferred g-4 V2 / g-7**: actual decision-boundary playback
  rendering. The infrastructure shipped by g-4 makes this a pure
  rendering refactor.
