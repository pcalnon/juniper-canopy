# Canopy-to-CasCor Connection Failure Analysis

**Date**: 2026-03-22
**Author**: Claude Code (Opus 4.6)
**Status**: Analysis complete, fixes validated, implementation pending

---

## Symptom

When juniper-canopy starts in service mode with `CASCOR_SERVICE_URL="http://localhost:8201"`,
the health probe **passes** but the `ServiceBackend` connection **fails**:

```bash
JuniperCascor reachable at http://localhost:8201 (21.3ms)
ServiceBackend failed to connect to http://localhost:8201
Backend initialized: service
```

Canopy continues running with a non-functional `ServiceBackend` — no training data flows,
the dashboard shows epoch 0 indefinitely.

---

## Root Causes

### RC-1: Response key mismatch in `is_ready()` (data contract bug)

**Severity**: Critical — `is_ready()` always returns `False` regardless of server state.

| Component                     | Key path                     | File                                      | Line |
|-------------------------------|------------------------------|-------------------------------------------|------|
| **cascor server** response    | `details.network_loaded`     | `juniper-cascor/src/api/routes/health.py` | 73   |
| **cascor-client** expectation | `data.network_loaded`        | `juniper-cascor-client/client.py`         | 76   |
| **cascor server** model       | `details: dict[str, object]` | `juniper-cascor/src/api/models/health.py` | 28   |

The client code:

```python
result = self._get("/health/ready")
return result.get("data", {}).get("network_loaded", False)  # WRONG: "data" → "details"
```

The server returns:

```python
ReadinessResponse(
    ...
    details={"network_loaded": network_loaded, "training_state": training_state},
)
```

**Impact**: `result.get("data", {})` returns `{}`, so `.get("network_loaded", False)` returns
`False` unconditionally. Every call to `is_ready()` fails, making `connect()` always return
`False`.

**Additional finding**: The cascor-client unit tests (`test_client.py:85-94`) mock the
`/v1/health/ready` response using an `_envelope()` wrapper that wraps data in
`{"status": "success", "data": {...}}`. But the server explicitly returns flat
`ReadinessResponse` objects — health endpoints are exempt from the `ResponseEnvelope`
wrapper, as documented in `health.py:8-10` and verified by cascor's own server tests
(`test_api_health.py:178-189`). The client tests pass against the wrong mock.

### RC-2: `connect()` gates on `network_loaded` instead of liveness

**Severity**: Medium — even with RC-1 fixed, a timing race exists.

`CascorServiceAdapter.connect()` calls `is_ready()` which requires `network_loaded == True`.
But the auto-start training creates the network as a background asyncio task. If canopy
starts before cascor's auto-start completes, `network_loaded` is still `False`.

Additionally, `connect()` checking for `network_loaded` is redundant — the subsequent
`attach_to_existing()` call in `ServiceBackend.initialize()` already handles the network
existence check separately.

| Operation              | What it checks                   | Should check                     |
|------------------------|----------------------------------|----------------------------------|
| `connect()`            | `is_ready()` → `network_loaded`  | `is_alive()` → service reachable |
| `attach_to_existing()` | `get_network()` → network exists | (correct as-is)                  |

**Validation**: Confirmed safe to change. No downstream code depends on `connect()`
returning True only when a network is loaded. The WebSocket relay (`/ws/training`) does
not require a pre-loaded network. Existing tests at
`test_cascor_service_adapter.py:356-378` need updating to mock `is_alive()` instead of
`is_ready()`.

### RC-3: `ServiceBackend.initialize()` failure is not handled (WILL NOT FIX)

**Severity**: Low — canopy runs in a broken state instead of falling back to demo mode.

`main.py:181` calls `await backend.initialize()` but does not check the return value.

**Validation result**: Will not fix. The existing fallback logic at `main.py:165-178`
already handles unreachable services by falling back to demo mode. With RC-1 and RC-2
fixed, the gap between the liveness probe (line 168) and `connect()` (line 123) is closed —
both now use the same liveness check. Adding another fallback at line 181 would duplicate
the existing path and risk double-initialization.

---

## Connection Flow Diagram

### Before fix (current broken state)

```bash
main.py startup
    |
    +-- probe_dependency("JuniperCascor", ".../v1/health/live")
    |   '-- HTTP GET /v1/health/live -> {"status": "alive"} -> PASS
    |
    +-- backend.initialize()
    |   +-- adapter.connect()
    |   |   '-- client.is_ready()
    |   |       '-- HTTP GET /v1/health/ready -> ReadinessResponse
    |   |           '-- result.get("data", {}).get("network_loaded", False)
    |   |               '-- "data" key missing -> returns False -> FAIL  [RC-1]
    |   |
    |   '-- (skipped because connect() returned False)
    |       +-- adapter.attach_to_existing()  <-- never reached
    |       '-- adapter.start_metrics_relay() <-- never reached
    |
    '-- canopy continues with broken ServiceBackend
```

### After fix

```bash
main.py startup
    |
    +-- probe_dependency("JuniperCascor", ".../v1/health/live")
    |   '-- HTTP GET /v1/health/live -> {"status": "alive"} -> PASS
    |
    +-- backend.initialize()
    |   +-- adapter.connect()
    |   |   '-- client.is_alive()
    |   |       '-- HTTP GET /v1/health/live -> 200 OK -> PASS  [RC-2 fix]
    |   |
    |   +-- adapter.attach_to_existing()
    |   |   '-- client.get_network() -> check for existing network
    |   |
    |   '-- adapter.start_metrics_relay()
    |       '-- WebSocket /ws/training -> streaming metrics
    |
    '-- "ServiceBackend connected to http://localhost:8201"
```

---

## Proposed Fixes

### Fix 1: Correct `is_ready()` key path (RC-1)

**File**: `juniper-cascor-client/juniper_cascor_client/client.py:76`

```python
# Before:
return result.get("data", {}).get("network_loaded", False)

# After:
return result.get("details", {}).get("network_loaded", False)
```

### Fix 1b: Fix client test mocks to match server response schema (RC-1)

**File**: `juniper-cascor-client/tests/test_client.py`

The existing `test_is_ready_true` and `test_is_ready_false` tests use `_envelope()`
which wraps in `{"status": "success", "data": {...}}`. These must be updated to use
the actual flat `ReadinessResponse` schema returned by the server.

### Fix 2: Use `is_alive()` in `connect()` (RC-2)

**File**: `juniper-canopy/src/backend/cascor_service_adapter.py:122-128`

```python
# Before:
async def connect(self) -> bool:
    """Connect to the CasCor service and verify it is ready."""
    try:
        return self._client.is_ready()
    except JuniperCascorClientError:
        logger.error(f"Failed to connect to CasCor service at {self._service_url}")
        return False

# After:
async def connect(self) -> bool:
    """Connect to the CasCor service and verify it is reachable."""
    try:
        return self._client.is_alive()
    except Exception:
        logger.error(f"Failed to connect to CasCor service at {self._service_url}")
        return False
```

Changes:

- `is_ready()` -> `is_alive()` — check liveness, not application state
- `JuniperCascorClientError` -> `Exception` — `is_alive()` catches `ConnectionError`
  which is not a subclass of `JuniperCascorClientError`
- Docstring updated

### Fix 2b: Update existing canopy adapter tests (RC-2)

**File**: `juniper-canopy/tests/test_cascor_service_adapter.py:356-378`

Update `TestAsyncConnect` tests to mock `is_alive()` instead of `is_ready()`.

---

## Test Plan

### T-1: Fix client `is_ready()` tests to use correct response schema (RC-1)

**File**: `juniper-cascor-client/tests/test_client.py`

Update existing `test_is_ready_true` and `test_is_ready_false` to mock the flat
`ReadinessResponse` schema (with `details` key) instead of envelope-wrapped responses.

### T-2: Update canopy `connect()` tests for `is_alive()` (RC-2)

**File**: `juniper-canopy/tests/test_cascor_service_adapter.py`

Update `TestAsyncConnect` tests:

- `test_connect_success`: mock `is_alive()` returning `True`
- `test_connect_not_ready`: mock `is_alive()` returning `False`
- `test_connect_on_error`: mock `is_alive()` raising `ConnectionError`

### T-3: Response contract test — cascor readiness schema

**File**: `juniper-cascor-client/tests/test_client.py` (extend)

Add a test that validates the expected response schema: `details` key present,
`data` key absent.

---

## Files Modified

| File                                                           | Change                                          | Root Cause |
|----------------------------------------------------------------|-------------------------------------------------|------------|
| `juniper-cascor-client/juniper_cascor_client/client.py:76`     | `"data"` -> `"details"`                         | RC-1       |
| `juniper-cascor-client/tests/test_client.py`                   | Fix `is_ready` test mocks to flat schema        | RC-1       |
| `juniper-canopy/src/backend/cascor_service_adapter.py:122-128` | `is_ready()` -> `is_alive()`, broaden exception | RC-2       |
| `juniper-canopy/tests/test_cascor_service_adapter.py:356-378`  | Update connect tests for `is_alive()`           | RC-2       |

---

## Verification Commands

After implementing fixes:

```bash
# 1. Run cascor-client unit tests
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v -k "is_ready or health"

# 2. Run canopy unit tests
cd /home/pcalnon/Development/python/Juniper/juniper-canopy
pytest tests/ -v -k "connect or adapter or service_backend"

# 3. Manual integration test
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
JUNIPER_CASCOR_PORT=8201 python server.py

# Terminal 2: Start canopy (should connect successfully)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --port 8050
# Expected: "ServiceBackend connected to http://localhost:8201" in logs

# 4. Verify readiness contract
curl -s http://localhost:8201/v1/health/ready | python3 -c "
import json, sys
r = json.load(sys.stdin)
assert 'details' in r, 'Missing details key'
print(f'network_loaded={r[\"details\"][\"network_loaded\"]}')
print(f'status={r[\"status\"]}')
print('Contract OK')
"
```
