# Investigation Plan: External CasCor Training Not Displayed in Canopy

**Version**: 1.0.0
**Date**: 2026-03-26
**Author**: Claude (AI Agent)
**Status**: Active Investigation

---

## Problem Statement

After implementing the Canopy → External CasCor connection (per
`CANOPY_EXTERNAL_CASCOR_PLAN.md`), juniper-canopy successfully connects to
an externally running juniper-cascor process. However, **no training data
from the external cascor process is displayed in the canopy frontend**.

The connection appears healthy (health checks pass, service mode activates),
but the dashboard renders empty metrics panels — no loss curves, no accuracy
plots, no epoch counters.

---

## Scope

This investigation covers the **complete data path** from the cascor server
through to the canopy frontend, across three codebases:

| Codebase | Role |
|----------|------|
| **juniper-cascor** | Source of training metrics (REST API + WebSocket broadcast) |
| **juniper-cascor-client** | HTTP/WebSocket client library |
| **juniper-canopy** | Consumer: backend adapter, relay, API endpoints, dashboard |

---

## Investigation Approach

### Strategy: End-to-End Data Path Tracing

Trace every path by which training data travels from cascor to the canopy
dashboard, identifying any point where data is lost, malformed, or silently
discarded.

### Two Primary Data Paths

```
PATH A — HTTP Polling (Primary Display Mechanism)
══════════════════════════════════════════════════
Dashboard (dcc.Interval, 1s)
  → GET /api/metrics/history?limit=N
    → main.py: backend.get_metrics_history(count)
      → ServiceBackend → _ServiceTrainingMonitor.get_recent_metrics(count)
        → JuniperCascorClient.get_metrics_history(count)
          → GET cascor:8200/v1/metrics/history?count=N
            → cascor: success_response(lifecycle.get_metrics_history(count))
              → ResponseEnvelope(status="success", data=[...metrics...], meta={...})
          ← response.json() → full envelope dict
        ← result.get("history", [])  ← UNWRAP POINT
      ← list (empty or populated)
    ← {"history": list}
  ← payload["history"]
→ Metrics panel renders from store


PATH B — WebSocket Relay (Real-Time Supplementary)
═══════════════════════════════════════════════════
cascor /ws/training broadcasts
  → CascorTrainingStream (websockets client)
    → CascorServiceAdapter._relay_loop()
      → websocket_manager.broadcast({type, data})
        → Canopy /ws/training connected dashboard clients
          → JavaScript websocket_client.js message buffer
            → (Not wired to Dash dcc.Store — supplementary only)
```

### Investigation Phases

| # | Phase | Objective | Files |
|---|-------|-----------|-------|
| 1 | **Response Envelope Analysis** | Verify cascor API response format vs canopy expectations | `cascor/api/models/common.py`, `cascor-client/client.py`, `canopy/backend/cascor_service_adapter.py` |
| 2 | **HTTP Polling Path Trace** | Trace metrics from cascor REST → dashboard render | `_ServiceTrainingMonitor`, `ServiceBackend`, `main.py`, `dashboard_manager.py` |
| 3 | **WebSocket Relay Path Trace** | Trace metrics from cascor WS → canopy WS → dashboard | `CascorTrainingStream`, `_relay_loop`, `websocket_manager`, `websocket_client.js` |
| 4 | **State Hydration Path Trace** | Verify initial state sync populates dashboard on connect | `CascorStateSync`, `ServiceBackend.initialize()`, `main.py lifespan` |
| 5 | **FakeCascorClient Fidelity** | Compare fake client response shapes vs real server | `fake_client.py`, `ResponseEnvelope` |
| 6 | **Frontend Consumption** | Verify dashboard correctly reads API responses | `dashboard_manager.py`, `metrics_panel.py` |

---

## Phase 1: Response Envelope Analysis

### Hypothesis

The cascor REST API wraps all responses in a `ResponseEnvelope`:

```json
{"status": "success", "data": <payload>, "meta": {"timestamp": ..., "version": "0.4.0"}}
```

The canopy adapter code may expect a **flat** or differently-structured
response, causing data extraction to fail silently (defaulting to empty
collections).

### Verification Steps

1. **Read** `cascor/api/models/common.py` — confirm `ResponseEnvelope` structure
2. **Read** `cascor-client/client.py` `_request()` — confirm client returns raw `response.json()` (no unwrapping)
3. **Read** `canopy/backend/cascor_service_adapter.py` `_ServiceTrainingMonitor` — check what keys it reads from responses
4. **Compare** expected keys vs actual envelope keys for each method:
   - `get_metrics_history()` — expects `"history"` key?
   - `get_metrics()` — expects flat metrics dict?
   - `get_training_status()` — expects `"is_training"` at top level?
5. **Read** `cascor-client/testing/fake_client.py` — check if fake responses match real envelope format

### Expected Outcome

Identify any methods where the canopy code reads keys that don't exist at
the expected level of the response envelope.

---

## Phase 2: HTTP Polling Path Trace

### Hypothesis

The dashboard's primary data path (HTTP polling every 1 second) returns
empty metrics because the adapter fails to unwrap the cascor API envelope.

### Verification Steps

1. **Trace** `GET /api/metrics/history` end-to-end:
   - `main.py:640-650` → `backend.get_metrics_history(count)`
   - `service_backend.py:106-107` → `self._adapter.training_monitor.get_recent_metrics(count)`
   - `cascor_service_adapter.py:74-77` → `self._client.get_metrics_history(count=count)`
   - Client returns envelope → adapter extracts `result.get("history", [])` — is "history" present?

2. **Trace** `GET /api/metrics`:
   - `main.py:630-637` → `backend.get_metrics()`
   - `service_backend.py:103-104` → `self._adapter.training_monitor.get_current_metrics()`
   - `cascor_service_adapter.py:68-72` → returns `self._client.get_metrics()` raw

3. **Trace** `GET /api/state`:
   - `main.py:583-615` — service mode branch
   - Uses `training_state.get_state()` + `backend._adapter.get_canopy_params()`
   - Verify `get_canopy_params()` unwraps correctly

4. **Verify** `dashboard_manager.py:1681-1711` — how it normalizes the API response

### Expected Outcome

Pinpoint the exact line(s) where metric data is lost due to incorrect
key access on the response envelope.

---

## Phase 3: WebSocket Relay Path Trace

### Hypothesis

The WebSocket relay may be functional but irrelevant to the display issue,
since the Dash dashboard uses HTTP polling (not WebSocket) as its primary
data source.

### Verification Steps

1. **Read** relay loop in `cascor_service_adapter.py:163-220`
2. **Confirm** relay broadcasts to `websocket_manager`
3. **Check** if any Dash callback reads from WebSocket messages (via `dcc.Store` or clientside callback)
4. **Check** `websocket_client.js` — does it update any Dash-accessible store?
5. **Determine** if WebSocket path is primary or supplementary for metrics display

### Expected Outcome

Confirm whether the WebSocket relay contributes to the metrics display
or is purely supplementary. If supplementary, the HTTP polling path is
the sole cause of the display failure.

---

## Phase 4: State Hydration Path Trace

### Hypothesis

The initial state sync (`CascorStateSync.sync()`) may also fail to extract
data from the response envelope, resulting in blank initial state even though
the sync "completes" without error (partial state tolerant).

### Verification Steps

1. **Read** `state_sync.py:43-98` — trace each fetch:
   - `get_training_status()` — reads `response.get("is_training", False)` and `response.get("data", {}).get("state", "idle")`
   - `get_training_params()` — reads `response.get("data", {}).get("params", {})`
   - `get_metrics_history()` — reads `response.get("data", {}).get("history", [])`
2. **Compare** each access pattern against the actual envelope structure
3. **Verify** that `_normalize_status()` handles the cascor state values correctly
4. **Check** if `ServiceBackend.initialize()` consumes synced state correctly

### Expected Outcome

Identify whether the state sync silently produces empty/default state due
to envelope mismatch, giving the appearance of a successful sync.

---

## Phase 5: FakeCascorClient Fidelity

### Hypothesis

Tests pass because `FakeCascorClient` returns a non-standard response
format that happens to match what the canopy code expects, but this
format diverges from the real cascor server's `ResponseEnvelope`.

### Verification Steps

1. **Compare** `FakeCascorClient.get_training_status()` response shape vs real cascor `/v1/training/status` response
2. **Compare** `FakeCascorClient.get_metrics_history()` response shape vs real cascor `/v1/metrics/history` response
3. **Compare** `FakeCascorClient.get_metrics()` response shape vs real cascor `/v1/metrics` response
4. **Document** all divergences

### Expected Outcome

Catalog all response format divergences between fake and real clients,
explaining why unit tests pass but real integration fails.

---

## Phase 6: Frontend Consumption

### Hypothesis

Even if the backend returns correct data, the frontend may fail to render
it due to unexpected data shapes or missing fields.

### Verification Steps

1. **Read** `dashboard_manager.py:1681-1711` — `_update_metrics_store_handler()`
2. **Verify** it handles the response from `GET /api/metrics/history`
3. **Read** `metrics_panel.py` — the callback that renders metrics from the store
4. **Check** what fields the metrics panel expects (epoch, loss, accuracy, etc.)
5. **Verify** the cascor metrics format matches what the panel expects

### Expected Outcome

Determine if the frontend correctly consumes whatever the backend provides,
or if there are additional format mismatches at the rendering layer.

---

## Artifacts

| Artifact | Location |
|----------|----------|
| This plan | `notes/INVESTIGATION_PLAN_EXTERNAL_CASCOR_METRICS_DISPLAY.md` |
| Findings | `notes/ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md` (to be created) |
| Original plan | `notes/CANOPY_EXTERNAL_CASCOR_PLAN.md` |

---

## Success Criteria

- All data paths traced end-to-end with evidence
- Root causes identified with file:line references
- Each root cause classified by severity and impact
- Recommended fixes documented for each root cause
- FakeCascorClient divergences cataloged
