# Independent Root Cause Analysis: Canopy-CasCor External Connection Failure

- **Version**: 1.0.0
- **Date**: 2026-03-27
- **Author**: Claude (Opus 4.6, AI Agent)
- **Status**: Analysis Complete
- **Scope**: Independent verification of Phase 2 findings + identification of additional root causes
- **Related**:
  - `UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN.md` — Phase 1 (all fixes implemented)
  - `ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY.md` — Phase 2 root cause identification
  - `ROOT_CAUSE_ANALYSIS_PHASE_3_EXTERNAL_CASCOR.md` — Prior Phase 3 analysis (separate agent)
- **Repositories Analyzed**: juniper-canopy, juniper-cascor, juniper-cascor-client

---

## 1. Executive Summary

This analysis independently verifies the Phase 2 root cause determination and identifies
additional issues missed by both prior debugging phases. The investigation confirmed all three
Phase 2 root causes through direct source code inspection across three repositories, and
discovered four additional contributing issues.

### Phase 2 Root Causes — Verification Results

| Phase 2 RC                                          | Claimed Severity | Verification  | Assessment                                     |
|-----------------------------------------------------|------------------|---------------|------------------------------------------------|
| RC-1: Metrics data format mismatch (flat vs nested) | CRITICAL         | **CONFIRMED** | Correctly identified as the primary blocker    |
| RC-2: WebSocket relay state callback omits fields   | MODERATE         | **CONFIRMED** | Correctly identified; severity appropriate     |
| RC-3: Dashboard ignores WebSocket relay             | LOW              | **CONFIRMED** | Correctly identified; not a functional blocker |

### Additional Root Causes Discovered

| ID       | Severity | Root Cause                                                               | Impact                                                  |
|----------|----------|--------------------------------------------------------------------------|---------------------------------------------------------|
| RC-4     | MODERATE | State sync metrics history stored without normalization                  | Latent bug; raw cascor field names preserved            |
| RC-5     | MODERATE | Cascor TrainingMonitor never updates `current_phase`                     | All metrics labeled "output" regardless of actual phase |
| ~~RC-6~~ | ~~LOW~~  | ~~Fallback-to-demo path doesn't re-sync training_state~~                 | ~~RETRACTED — see Section 4.3~~                         |
| RC-7     | LOW      | Phase 1 tests validate normalization output, not dashboard compatibility | Test coverage gap that allowed RC-1 to persist          |

### Key Finding

**The Phase 2 analysis correctly identified the primary blocker (RC-1).** Fixing RC-1 alone
would make the dashboard display external cascor training metrics. The additional issues affect
data correctness (RC-4, RC-5), edge-case resilience (RC-6), and test coverage (RC-7).

---

## 2. Methodology

### Approach

1. Read and analyzed both Phase 1 and Phase 2 debugging documentation in full
2. Deployed parallel specialized exploration agents to map the complete data pipeline across
   juniper-canopy, juniper-cascor, and juniper-cascor-client
3. Independently read each source file cited in the Phase 2 analysis to verify every claim
4. Traced the complete data flow from cascor REST API through to dashboard rendering
5. Compared service mode and demo mode data paths side-by-side at every layer
6. Searched for additional issues in areas not covered by Phase 2 analysis
7. Cross-validated findings between exploration agents for consistency

### Files Examined

| File                                         | Repository    | Lines Examined | Purpose                                               |
|----------------------------------------------|---------------|----------------|-------------------------------------------------------|
| `frontend/components/metrics_panel.py`       | canopy        | 1080-1580      | Dashboard metrics rendering (9 nested-key read sites) |
| `backend/cascor_service_adapter.py`          | canopy        | 70-460         | Normalization boundary, relay, WebSocket handler      |
| `backend/service_backend.py`                 | canopy        | 90-210         | Service mode backend interface                        |
| `backend/state_sync.py`                      | canopy        | 1-155 (full)   | Initial state synchronization                         |
| `frontend/dashboard_manager.py`              | canopy        | 1500-1730      | Status bar + metrics polling                          |
| `demo_mode.py`                               | canopy        | 1130-1200      | Demo metrics format (reference)                       |
| `main.py`                                    | canopy        | 135-220        | Lifespan, state sync, callbacks                       |
| `backend/training_state_machine.py`          | canopy        | 38-45          | TrainingPhase enum definition                         |
| `api/lifecycle/monitor.py`                   | cascor        | 100-200        | Training metrics recording, phase tracking            |
| `api/lifecycle/manager.py`                   | cascor        | 215-290        | Phase transitions, monitoring hooks                   |
| `api/lifecycle/state_machine.py`             | cascor        | 55-220         | FSM phases, enum names                                |
| `client.py`                                  | cascor-client | 170-215        | REST client methods                                   |
| `ws_client.py`                               | cascor-client | 60-75          | WebSocket client                                      |
| `tests/unit/test_response_normalization.py`  | canopy        | 1-120          | Phase 1 characterization tests                        |
| `tests/fixtures/cascor_response_fixtures.py` | canopy        | (referenced)   | Test fixtures                                         |

---

## 3. Phase 2 Root Cause Verification

### 3.1 RC-1: Metrics Data Format Mismatch — CONFIRMED (CRITICAL)

**Phase 2 claim**: `_normalize_metric()` produces flat keys (`train_loss`, `train_accuracy`,
`hidden_units`), but `MetricsPanel` reads nested keys (`metrics.loss`, `metrics.accuracy`,
`network_topology.hidden_units`).

**Independent verification**:

**Producer** — `cascor_service_adapter.py:439-460`:

```python
# _normalize_metric() output — FLAT keys
return {
    "epoch": entry.get("epoch", 0),
    "train_loss": ...,
    "train_accuracy": ...,
    "val_loss": ...,
    "val_accuracy": ...,
    "hidden_units": ...,
    "phase": ...,
    "timestamp": ...,
}
```

**Consumer** — `metrics_panel.py` (9 locations expecting NESTED keys):

| Line    | Code                                                                     | Expected Structure                   |
|---------|--------------------------------------------------------------------------|--------------------------------------|
| 1091    | `m.get("network_topology", {}).get("hidden_units", 0)`                   | `network_topology.hidden_units`      |
| 1120    | `latest.get("metrics", {}).get("loss", 0)`                               | `metrics.loss`                       |
| 1121    | `latest.get("metrics", {}).get("accuracy", 0)`                           | `metrics.accuracy`                   |
| 1122    | `latest.get("network_topology", {}).get("hidden_units", 0)`              | `network_topology.hidden_units`      |
| 1330    | `metric.get("metrics", {}).get("loss", 0)`                               | `metrics.loss` (in `_parse_metrics`) |
| 1449    | `metrics_data[i-1].get("network_topology", {}).get("hidden_units", 0)`   | `network_topology.hidden_units`      |
| 1450    | `metrics_data[i].get("network_topology", {}).get("hidden_units", 0)`     | `network_topology.hidden_units`      |
| 1499    | `metric.get("metrics", {}).get("accuracy", 0)`                           | `metrics.accuracy`                   |
| 1561-62 | `metrics_data[i-1/i].get("network_topology", {}).get("hidden_units", 0)` | `network_topology.hidden_units`      |

**Demo mode reference** (`demo_mode.py:1162-1177`):

```python
# Demo mode output — NESTED keys (what the dashboard expects)
metrics = {
    "epoch": self.current_epoch,
    "metrics": {
        "loss": float(loss),
        "accuracy": float(accuracy),
        "val_loss": float(val_loss),
        "val_accuracy": float(val_accuracy),
    },
    "network_topology": {
        "input_units": self.network.input_size,
        "hidden_units": len(self.network.hidden_units),
        "output_units": self.network.output_size,
    },
    "phase": phase_name,
    "timestamp": datetime.now().isoformat(),
}
```

**Runtime consequence**: Every `.get("metrics", {}).get("loss", 0)` chain returns `0` because
the flat dict has no `"metrics"` key. Loss plots, accuracy plots, current value displays, and
hidden unit markers all render zero or empty.

**Verdict**: Phase 2 is **correct**. This is the primary and only display-blocking root cause.

---

### 3.2 RC-2: WebSocket Relay State Callback Omits Fields — CONFIRMED (MODERATE)

**Phase 2 claim**: Relay callback only forwards `status` and `phase`, discarding
`current_epoch`, `max_epochs`, etc.

**Verification** — `cascor_service_adapter.py:218-225`:

```python
if msg_type == "state" and self._state_update_callback and isinstance(data, dict):
    try:
        from backend.state_sync import CascorStateSync
        status = CascorStateSync._normalize_status(data.get("status", data.get("state", "")))
        self._state_update_callback(status=status, phase=data.get("phase", ""))
        # ^^^ Only status and phase — no current_epoch, no hidden_units
    except Exception as se:
        logger.debug(f"State update callback error: {se}")
```

**Mitigating factor**: The status bar reads from `/api/status` which makes a fresh REST call
each poll. The `/api/state` endpoint is affected but is secondary.

**Verdict**: Phase 2 is **correct**.

---

### 3.3 RC-3: Dashboard Ignores WebSocket Relay — CONFIRMED (LOW)

**Verification** — `dashboard_manager.py:1681-1710` confirms HTTP polling:

```python
url = self._api_url(f"/api/metrics/history?limit={limit}")
response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
```

No Dash callback reads from the `websocket-data` div. 1-second polling is adequate.

**Verdict**: Phase 2 is **correct**.

---

## 4. Additional Root Causes Discovered

### 4.1 RC-4: State Sync Metrics History Not Normalized (MODERATE)

**Location**: `state_sync.py:115-127`

**Problem**: During initial state sync, `CascorStateSync.sync()` stores raw cascor metrics
without any normalization:

```python
# state_sync.py:121
state.metrics_history = data  # Raw cascor format — NOT normalized
```

Raw cascor metrics use native field names (`loss`, `accuracy`, `validation_loss`,
`validation_accuracy`) — different from both the canopy canonical flat format (`train_loss`,
`train_accuracy`) AND the demo mode nested format (`metrics.loss`).

**Current impact**: LOW — `synced.metrics_history` is stored in `ServiceBackend._synced_state`
but never served to the dashboard. The dashboard polling path (`GET /api/metrics/history` →
`ServiceBackend.get_metrics_history()`) makes fresh REST calls that go through normalization.

**Verification**: Traced all usages of `synced.metrics_history` and `get_synced_state()`:

- `main.py:190-200` reads `synced.status`, `synced.phase`, `synced.current_epoch` — but
  never references `synced.metrics_history`
- No other code path serves `synced.metrics_history` to the dashboard

**Latent risk**: If any future code path serves initial metrics from the synced state (e.g.,
to avoid a cold-start empty chart), the data would be in the wrong format. This should be
normalized for consistency.

---

### 4.2 RC-5: Cascor TrainingMonitor Never Updates current_phase (MODERATE)

**Location**: `juniper-cascor/src/api/lifecycle/monitor.py:111`

**Problem**: The `TrainingMonitor.current_phase` is initialized to `"output"` and **never
updated** during training:

```python
# monitor.py:111 — only assignment in the entire codebase
self.current_phase = "output"
```

When training enters candidate phase, the `TrainingLifecycleManager` updates `training_state`
(manager.py:270: `state.update_state(phase="Candidate")`) and `state_machine`, but NOT
`monitor.current_phase`. Since metrics are recorded via `monitor.on_epoch_end()` which reads
`self.current_phase` (monitor.py:171), **all metrics history entries have `phase: "output"`
regardless of actual training phase**.

**Verification**: Searched all assignments to `current_phase` across the entire cascor
codebase — only one assignment found (the initialization at monitor.py:111).

**Impact on canopy**:

- Phase-colored scatter plots (`metrics_panel.py:1340-1343`) will show all data as "Output
  Training" — no data under "Candidate Training"
- The dashboard uses substring matching (`"output" in phase`, `"candidate" in phase`) for
  phase filtering — candidate data will never appear because all metrics are labeled "output"
- **This is a juniper-cascor bug**, not a juniper-canopy bug
- Not a display blocker (data still shows, just with wrong phase labels)

---

### 4.3 ~~RC-6: Fallback-to-Demo Path Missing State Re-sync~~ (RETRACTED)

**Status**: RETRACTED after validation review.

**Original claim**: When cascor health check fails at startup, fallback to demo mode doesn't
re-sync the global `training_state`.

**Correction**: The lifespan function is an `@asynccontextmanager` that runs sequentially,
not iteratively. After the fallback at lines 172-177 replaces `backend` with a demo backend,
execution continues to line 180 (`await backend.initialize()`), then reaches lines 183-202
where `backend.backend_type` IS `"demo"`, so the `if` at line 183 WOULD match and the demo
state sync WOULD execute correctly. The described failure mode does not occur.

**Note**: There is a real (but minor) issue in this path: `backend.initialize()` is called
twice — once at line 177 (inside the fallback block) and again at line 180 (unconditionally).
This is a code smell but not functionally harmful since demo initialization is idempotent.

---

### 4.4 RC-7: Phase 1 Test Coverage Gap (LOW)

**Location**: `tests/unit/test_response_normalization.py`

**Problem**: Phase 1 characterization tests validate that normalization produces correct flat
output but don't verify compatibility with the dashboard's expected nested format:

```python
# test_response_normalization.py:96
assert "train_loss" in result[0] or "loss" in result[0]
# Validates FLAT key existence — correct for normalization layer
# But never validates that MetricsPanel can read this format
```

**Why this matters**: This test coverage gap is the reason RC-1 persisted through the entire
Phase 1 development cycle. The Phase 1 plan defined a "Canonical Internal Contract" (Section
6.2) with flat keys, wrote tests validating flat key production, confirmed all tests pass —
but never tested whether the dashboard could actually consume those flat keys.

The critical insight: the Phase 1 plan's "canonical contract" was designed by analyzing the
normalization boundary (cascor → canopy), not by analyzing the consumption boundary (canopy →
dashboard). The status bar reads flat keys and was working, which gave false confidence that
the contract was correct. But the metrics panel reads nested keys (matching demo mode's
format), which is a different contract entirely.

---

## 5. Complete Data Flow Comparison

### 5.1 Service Mode Metrics (BROKEN)

```bash
cascor TrainingMonitor.on_epoch_end()
  → {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase:"output"}
  → wrapped in ResponseEnvelope

JuniperCascorClient.get_metrics_history()
  → returns raw ResponseEnvelope

_ServiceTrainingMonitor.get_recent_metrics()
  → unwraps envelope → normalizes each entry
  → FLAT: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units, phase}
  ✓ Correctly unwraps and normalizes field names

ServiceBackend.get_metrics_history() → passes through FLAT list
GET /api/metrics/history → {"history": [FLAT]}
dashboard_manager → stores FLAT list in Dash Store

MetricsPanel reads:
  metric.get("metrics", {}).get("loss", 0) → returns 0 ✗
  metric.get("network_topology", {}).get("hidden_units", 0) → returns 0 ✗
```

### 5.2 Demo Mode Metrics (WORKING)

```bash
DemoMode._emit_training_metrics()
  → NESTED: {epoch, metrics: {loss, accuracy, ...}, network_topology: {hidden_units, ...}, phase}

DemoBackend.get_metrics_history() → returns NESTED list
GET /api/metrics/history → {"history": [NESTED]}

MetricsPanel reads:
  metric.get("metrics", {}).get("loss", 0) → returns actual value ✓
  metric.get("network_topology", {}).get("hidden_units", 0) → returns actual value ✓
```

### 5.3 Status Bar (WORKING in both modes)

```bash
ServiceBackend.get_status()
  → transforms nested cascor response to flat: {is_running, is_paused, phase, current_epoch, hidden_units}

dashboard_manager._build_unified_status_bar_content()
  → reads: status_data.get("is_running") ✓
  → reads: status_data.get("current_epoch") ✓
  → reads: status_data.get("hidden_units") ✓
```

---

## 6. Why Prior Debugging Phases Failed to Resolve This

### Phase 1 Failure Mode

The Phase 1 plan correctly identified the systemic root cause (ResponseEnvelope format
divergence between `FakeCascorClient` and real cascor) and designed a comprehensive
normalization boundary. **All 13 fixes were correctly implemented.**

**Where it went wrong**: The plan defined a "Canonical Internal Contract" with flat keys by
analyzing what cascor sends → what canopy should normalize to. It never validated this
contract against what the dashboard actually reads. The status bar (flat keys) was working,
creating false confidence that flat keys were the correct target format. But the metrics panel
was built against demo mode's nested format — a different contract.

### Phase 2 Accuracy

The Phase 2 analysis correctly diagnosed this gap. Its conclusion — "the plan defined a
canonical contract but never reconciled the normalization layer's output format with the
dashboard's input format" — is precisely accurate and well-evidenced.

---

## 7. Consolidated Root Cause Summary

| ID       | Source            | Severity     | Root Cause                                    | Display Blocker?      | Fix Location                                                |
|----------|-------------------|--------------|-----------------------------------------------|-----------------------|-------------------------------------------------------------|
| RC-1     | Phase 2           | **CRITICAL** | Metrics flat vs nested mismatch               | **YES**               | canopy: `cascor_service_adapter.py` or `service_backend.py` |
| RC-2     | Phase 2           | MODERATE     | WebSocket relay callback omits fields         | No                    | canopy: `cascor_service_adapter.py:218-225`                 |
| RC-3     | Phase 2           | LOW          | Dashboard ignores WebSocket relay             | No                    | canopy: future enhancement                                  |
| RC-4     | **This analysis** | MODERATE     | State sync metrics not normalized             | No (dead path)        | canopy: `state_sync.py:121`                                 |
| RC-5     | **This analysis** | MODERATE     | Cascor monitor phase never updated            | No (data correctness) | **cascor**: `api/lifecycle/monitor.py` + `manager.py`       |
| ~~RC-6~~ | ~~This analysis~~ | ~~LOW~~      | ~~Fallback-to-demo missing state re-sync~~    | —                     | **RETRACTED** (validation disproved)                        |
| RC-7     | **This analysis** | LOW          | Phase 1 tests don't validate dashboard format | No (test gap)         | canopy: `tests/unit/test_response_normalization.py`         |

**Only RC-1 is a display-blocking issue.** Fixing RC-1 alone would make the dashboard display
external cascor training metrics correctly.

---

## 8. Fix Recommendations

### Priority 1 — Fix RC-1 (Resolves the visible failure)

**Recommended approach**: Option A from Phase 2 — add a transformation after
`_normalize_metric()` to produce the nested format the dashboard expects.

```python
@staticmethod
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format.

    Matches the format produced by DemoMode._emit_training_metrics().
    """
    return {
        "epoch": flat.get("epoch", 0),
        "metrics": {
            "loss": flat.get("train_loss"),
            "accuracy": flat.get("train_accuracy"),
            "val_loss": flat.get("val_loss"),
            "val_accuracy": flat.get("val_accuracy"),
        },
        "network_topology": {
            "hidden_units": flat.get("hidden_units", 0),
        },
        "phase": flat.get("phase"),
        "timestamp": flat.get("timestamp"),
    }
```

**Apply in**: `_ServiceTrainingMonitor.get_recent_metrics()` and `get_current_metrics()`,
wrapping results after `_normalize_metric()`.

**Advantages**:

- Single location change (1 new function + 2 call sites)
- Dashboard code untouched
- Demo mode path unaffected
- Maintains existing normalization boundary architecture

**Risks**:

- LOW: Must preserve falsy-but-valid values (epoch=0, loss=0.0)
- The `_first_defined()` helper already handles this correctly

### Priority 2 — Fix RC-5 (Cascor-side phase tracking)

**Approach**: Update `monitor.current_phase` in the cascor `TrainingLifecycleManager` when
phase transitions occur. This is a cross-repo change in juniper-cascor.

### Priority 3 — Fix RC-2 (Forward relay fields)

**Approach**: Extend the relay callback to forward `current_epoch`, `hidden_units`, and
other fields from cascor state messages.

### Priority 4 — Fix RC-4, RC-7 (Latent bugs + test gap)

**RC-4**: Apply `_normalize_metric()` + `_to_dashboard_metric()` to `SyncedState.metrics_history`.
**RC-7**: Add end-to-end contract test comparing service and demo output formats.

### ~~Priority 5 — Fix RC-6~~ (RETRACTED)

RC-6 was retracted after validation review (see Section 4.3). The fallback-to-demo path
does correctly re-sync training_state. The only minor issue is a double `initialize()` call.

---

## 9. Risk Assessment

| Risk                                        | Impact               | Probability | Mitigation                                                  |
|---------------------------------------------|----------------------|-------------|-------------------------------------------------------------|
| RC-1 fix introduces regression in demo mode | Charts break in demo | Low         | `_to_dashboard_metric()` only applies in service path       |
| Falsy values (0, 0.0) treated as missing    | Charts show gaps     | Medium      | Use `_first_defined()` + `"key" in dict` (already in place) |
| RC-5 fix requires cascor release            | Delays complete fix  | Medium      | RC-5 is non-blocking; can ship RC-1 fix independently       |
| Multiple fixes interact unexpectedly        | Unexpected behavior  | Low         | Fix in priority order; test each independently              |
| Analysis contains errors                    | Wrong fix applied    | Low         | RC-6 was retracted after validation; remaining RCs verified |

---

## 10. Guardrails

1. **End-to-end contract test**: After fixing RC-1, add a test that constructs a cascor
   ResponseEnvelope, passes it through the full service path, and verifies the output has
   `metrics.loss` and `network_topology.hidden_units` nested keys.

2. **Backend parity test**: Add a test comparing `ServiceBackend.get_metrics_history()` output
   structure against `DemoBackend.get_metrics_history()` output structure — they must match.

3. **Phase 1 test update**: Update `test_response_normalization.py` to verify nested output
   format, not just flat key presence.

4. **Visual smoke test**: After fix deployment, manually verify loss/accuracy charts display
   real training curves, not flat lines at zero.

---

## 11. Evidence Collection Index

| Evidence                       | File                             | Lines                                       | What It Proves                                                       |
|--------------------------------|----------------------------------|---------------------------------------------|----------------------------------------------------------------------|
| Flat key production            | `cascor_service_adapter.py`      | 439-460                                     | `_normalize_metric()` outputs flat keys                              |
| Nested key consumption         | `metrics_panel.py`               | 1091, 1120-22, 1330, 1449-50, 1499, 1561-62 | Dashboard expects nested keys at 9 sites                             |
| Demo nested format             | `demo_mode.py`                   | 1162-1177                                   | Demo mode produces nested format                                     |
| Status bar flat format         | `dashboard_manager.py`           | 1526-1532                                   | Status bar reads flat keys (works correctly)                         |
| Service status transform       | `service_backend.py`             | 100-136                                     | Correctly produces flat status dict                                  |
| Relay callback limited         | `cascor_service_adapter.py`      | 218-225                                     | Only status+phase forwarded                                          |
| State sync raw metrics         | `state_sync.py`                  | 121                                         | `state.metrics_history = data` without normalization                 |
| Cascor phase static            | `monitor.py` (cascor)            | 111                                         | `current_phase = "output"` never updated                             |
| Phase transitions skip monitor | `manager.py` (cascor)            | 270                                         | `state.update_state(phase="Candidate")` — state updated, monitor not |
| Test format gap                | `test_response_normalization.py` | 96                                          | Tests check flat keys only                                           |
| Polling handler                | `dashboard_manager.py`           | 1681-1710                                   | HTTP-only metrics fetch                                              |
| Fallback path                  | `main.py`                        | 165-177, 183-202                            | RETRACTED: state sync does execute after fallback                    |
| Client passthrough             | `client.py` (cascor-client)      | 202-211                                     | Returns raw ResponseEnvelope                                         |
| Adapter unwrap                 | `cascor_service_adapter.py`      | 408-418                                     | `_unwrap_response()` correctly strips envelope                       |
| Monitor get_recent_metrics     | `cascor_service_adapter.py`      | 96-108                                      | Correctly unwraps + normalizes to flat                               |
| Phase substring matching       | `metrics_panel.py`               | 1340-1343, 1502                             | Dashboard uses `"output" in phase` filtering                         |
