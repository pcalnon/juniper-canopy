# juniper-canopy — Histogram Bucket Rationale

**Date:** 2026-05-02
**METRICS-MON sub-track:** R4.1 / seed-14
**Status:** Initial draft — bucket layouts marked **tentative pending R5.1**.
**Related:** [`METRICS_MONITORING_R4_ENTRY_PLAN_2026-05-01.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R4_ENTRY_PLAN_2026-05-01.md) §3 Q1 (hybrid: document current rationale now; mark tentative; R5.1 ratifies).

---

## 1. Inventory

juniper-canopy exposes **one** Prometheus histogram on the production
surface (other shapes are Counters / Gauges).

| Metric | Labels | Bucket layout | Purpose |
|---|---|---|---|
| `canopy_ws_browser_latency_ms` | `endpoint` | `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]` (ms) | Browser-reported WebSocket round-trip latency, sampled by frontend instrumentation and POSTed back to canopy for aggregation. The `endpoint` label is the WebSocket channel ("training", "control"). |

Note: the unit is **milliseconds**, not seconds — the metric name
includes the explicit `_ms` suffix per Prometheus naming convention.

(Other histograms exist in the dashboard's `dataset_plotter`
component — `plotly.go.Histogram` for feature distributions — but
those are Plotly client-side visualizations, not Prometheus metrics.)

---

## 2. `canopy_ws_browser_latency_ms`

### 2.1 Current bucket layout

```python
buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
```

10 buckets (Prometheus appends an implicit `+inf`). Boundaries span
3 orders of magnitude (5 ms → 5 s).

### 2.2 Rationale per boundary

| Boundary (ms) | What it discriminates | SLO target served | R5.1 status |
|---|---|---|---|
| **5** | Sub-frame latency on a 200 Hz refresh — local-network round-trip. | Useful as the "ideal" floor; no SLO directly references it. | **Tentative.** May be removable if no SLO references "p50 < 5 ms". |
| **10** | One frame at 100 Hz. The training panel pushes metric updates at ≤10 Hz, so 10 ms RTT means update arrived before next display tick. | **Candidate** for "p50 WS RTT < 10 ms" SLO if R5.1 defines one for the training-WS channel. | **Tentative — moderate confidence.** |
| **25** | One frame at 60 Hz (~16 ms) — the typical display refresh boundary. RTT above this can cause visible UI jitter on the live training plot. | **Strong candidate** for "p95 WS RTT < 25 ms" SLO on the training channel. | **Tentative — high confidence.** |
| **50** | Crosses the human-perceptible interaction-lag threshold (~50 ms is the lower bound of perceived "instant"). Above this, control-channel commands (`pause`, `resume`) start to feel laggy. | **Candidate** for "p95 WS RTT < 50 ms" on the control channel. | **Tentative — high confidence.** |
| **100** | "Noticeable lag" threshold for human interaction (per Nielsen's classic UX research). Above this, the user perceives delay. | **Strong candidate** for "p99 WS RTT < 100 ms" SLO. | **Tentative — high confidence.** |
| **250** | One quarter-second; the boundary where users start to feel "sluggish". | Useful for capacity-planning queries (rate of >250 ms RTTs as a degradation signal). | **Tentative.** |
| **500** | Half-second; clear "lag" territory. Above this, the WebSocket connection is at risk of triggering the user's reload reflex. | **Candidate** for an alerting threshold ("rate of >500 ms RTTs > 1/min for 5 min → page on-call"). | **Tentative — moderate confidence.** |
| **1000** | Full second. WS RTTs above this typically indicate either upstream backpressure (cascor's broadcast loop saturated) or network egress contention. | Useful for distinguishing healthy slow-network from genuine system distress. | **Tentative.** |
| **2500** | 2.5 seconds. At this latency the browser will likely have already reconnected via the application-level heartbeat (cascor's WS Phase F sends ping every 30 s, pong-timeout 10 s — so pong-RTTs at 2.5 s are well within heartbeat tolerance but very degraded). | Pathological; useful for alerting only. | **Tentative.** |
| **5000** | Outer bound. Anything past 5 s is essentially a "session lost" indicator and the next observation will probably never arrive. | Filler for the `+inf` tail. | **Tentative.** May be redundant with `+inf`. |
| **+inf** | Mandatory upper bound; `histogram_quantile` requires it. | — | Required. |

### 2.3 Trade-off

The current layout was chosen with the human-UX latency thresholds in
mind (10 ms / 25 ms / 50 ms / 100 ms — the classic "ideal / good /
acceptable / lag" gradient). The 3-decade spread is appropriate for
WS RTT distributions but makes the upper bound (5 s) somewhat
redundant with `+inf` since RTTs that high typically reconnect before
the next observation. R5.1 should consider whether to drop the 2.5 s
and 5 s buckets in favor of denser resolution in the 25–500 ms region
where the load-bearing SLOs probably sit.

---

## 3. R5.1 ratification queue

When R5.1 designs the canopy SLO catalog:

- [ ] Decide whether "p95 training-WS RTT < 25 ms" is a load-bearing
      SLO (the live training plot is the primary user-facing
      experience).
- [ ] Decide whether "p99 control-WS RTT < 100 ms" is a separate SLO
      (control commands are user-initiated; perceived responsiveness
      matters more than absolute latency).
- [ ] Re-evaluate the 5 ms boundary — currently tentative; may be
      removable if no SLO references it and the bucket is consistently
      empty in production.
- [ ] Consider whether to split labels by channel (training vs control)
      into separate metric families for clearer SLO mapping, or keep
      the single metric with an `endpoint` label.

---

## 4. Process notes

- HELP-string marker: `canopy_ws_browser_latency_ms` carries a
  "tentative pending R5.1" suffix on its HELP line as a forward-pointer
  to this doc. Operators reading `/metrics` directly see the marker.
- Re-bucketing is a metric-version event but **not** a public-API
  break. No SemVer-major beat is required when R5.1 ratifies or
  reshapes.
