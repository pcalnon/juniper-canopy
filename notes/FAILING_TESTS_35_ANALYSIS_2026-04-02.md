# Failing Tests Analysis — 35 Test Failures

**Date**: 2026-04-02
**Branch**: `fix/failing-tests-35`
**Test Run**: 35 failed, 4184 passed, 6 skipped in 759.62s

---

## Executive Summary

35 test failures across 4 test files trace to 3 distinct root causes. All failures are in the test infrastructure or a single production code bug — no issues with core application logic.

---

## Failure Categories

### Category 1: Cassandra Integration Tests (11 failures)

**File**: `src/tests/integration/test_cassandra_real_instance.py`
**Classes**: `TestCassandraRealConnection`, `TestCassandraRealMetrics`, `TestCassandraRealLifecycle`

**Symptoms**:

- `_is_connected()` returns `False`
- Status returns `UNAVAILABLE` instead of `UP`
- Details dict missing `hosts`, `cluster_name`, `protocol_version`
- Only has `{'contact_points': ['127.0.0.1'], 'driver_available': False, 'port': 9042}`

**Root Cause**: The `cassandra-driver` Python package is not installed in the test environment. Tests have a proper `requires_cassandra` pytest marker and a `skipif` guard on `CASSANDRA_INTEGRATION_TEST=1`, but the `pytest_collection_modifyitems` function in `conftest.py` does **not** have a handler to skip tests when the driver library is missing. The marker is registered (line 133) but never acted upon for library availability.

**Fix**: Add a `requires_cassandra` handler in `pytest_collection_modifyitems` that attempts to `import cassandra` and skips all marked tests if the import fails.

---

### Category 2: Redis Integration Tests (11 failures)

**File**: `src/tests/integration/test_redis_real_instance.py`
**Classes**: `TestRedisRealConnection`, `TestRedisRealMetrics`, `TestRedisRealLifecycle`

**Symptoms**:

- `is_available()` returns `False`
- Status returns `DISABLED` instead of `UP`
- Details dict missing `version`, `uptime_seconds`, `connected_clients`
- Only has `{'install_hint': 'pip install redis', 'redis_available': False}`
- Log: "Redis library not installed - Redis integration disabled"

**Root Cause**: Identical pattern to Cassandra. The `redis` Python package is not installed. Tests have `requires_redis` marker and `skipif` guard on `REDIS_INTEGRATION_TEST=1`, but `pytest_collection_modifyitems` has no handler for library availability.

**Fix**: Add a `requires_redis` handler in `pytest_collection_modifyitems` that attempts to `import redis` and skips all marked tests if the import fails.

---

### Category 3: JuniperData E2E Tests (10 failures)

**File**: `src/tests/integration/test_juniper_data_e2e.py`
**Class**: `TestLiveServiceE2E`

**Symptoms**:

- All method calls return `MagicMock` objects instead of real data
- `health_check()` returns MagicMock, not `{"status": "healthy"}`
- `create_dataset()` returns MagicMock, not dict with `dataset_id`
- `download_artifact_npz().keys()` returns empty set
- Error-raising tests don't raise expected exceptions

**Root Cause**: The session-scoped `mock_juniper_data_client` fixture (conftest.py:194) patches `JuniperDataClient` globally. The mock is configured with correct return values on `mock_client_instance`. However, the `live_client` fixture (test file line 135) uses `JuniperDataClient` as a context manager:

```python
with JuniperDataClient(base_url=...) as client:
    yield client
```

When `__enter__()` is called on a `MagicMock`, it returns a **new, unconfigured MagicMock** — not the instance with configured return values. All subsequent method calls hit this bare MagicMock.

Additionally, the mock lacked:

- `list_generators` return value
- `download_artifact_bytes` return value
- Error-raising behavior for invalid inputs
- `generator` field in `create_dataset` response

**Fix**:

1. Configure `__enter__.return_value = mock_client_instance` and `__exit__.return_value = False`
2. Replace fixed `return_value` with `side_effect` functions for input-dependent behavior
3. Track created dataset IDs to raise `JuniperDataNotFoundError` for unknown IDs
4. Generate valid NPZ bytes using `np.savez` for `download_artifact_bytes`

---

### Category 4: Training Loop Tests (2 failures)

**File**: `src/tests/unit/test_phase6_implementation.py`
**Class**: `TestEndToEndTrainingLoop`

**Symptoms**:

- `demo.thread.is_alive()` still `True` after 90s join timeout
- Log shows "Training complete: reached max_epochs=300 during initial training"
- State machine transitions to COMPLETED
- But cascade units continue being installed afterward
- Warnings: "Cannot set phase to OUTPUT while status is STOPPED"

**Root Cause**: **Deadlock** in `_training_loop()` method of `demo_mode.py`.

At line 1126-1132, when Phase 1 reaches `max_epochs`, the code calls `_update_training_status()` from **inside** a `with self._lock:` block:

```python
with self._lock:                          # ← acquires Lock
    if self.current_epoch >= self.max_epochs:
        self.state_machine.mark_completed()
        self._update_training_status()    # ← tries to acquire same Lock → DEADLOCK
        self.is_running = False
        return                            # ← never reached
```

`_update_training_status()` (line 624) itself acquires `self._lock`:

```python
def _update_training_status(self):
    if not self.training_state:
        return
    with self._lock:                      # ← Lock is non-reentrant → blocks forever
        self._update_candidate_pool_state()
```

Since `self._lock` is `threading.Lock()` (not `RLock()`), attempting to acquire it while already held by the same thread causes permanent deadlock. The thread never exits, `is_running` is never set to `False`, and `thread.join(timeout=90)` times out.

**Fix**: Set a flag inside the lock block, then call `_update_training_status()` after releasing the lock:

```python
phase1_done = False
with self._lock:
    if self.current_epoch >= self.max_epochs:
        self.state_machine.mark_completed()
        self.is_running = False
        phase1_done = True
if phase1_done:
    self._update_training_status()
    return
```

---

## Development Plan

### Priority Order

1. **P0 — Deadlock fix** (Category 4): Production code bug affecting training loop
2. **P0 — Mock context manager** (Category 3): Session-scoped fixture affecting all mock-dependent tests
3. **P1 — Integration test skips** (Categories 1 & 2): Test infrastructure gap

### Implementation Steps

| Step | File | Change | Tests Affected |
|------|------|--------|---------------|
| 1 | `src/demo_mode.py:1126` | Move `_update_training_status()` outside lock block | 2 |
| 2 | `src/tests/conftest.py:228` | Fix mock context manager + side_effects | 10 |
| 3 | `src/tests/conftest.py:184` | Add cassandra/redis skip handlers | 22 |

### Validation Plan

1. Run full test suite: `pytest src/tests/ -v`
2. Verify all 35 previously-failing tests now pass (or skip gracefully for integration tests)
3. Verify no regressions in the 4184 previously-passing tests
4. Verify 6 previously-skipped tests remain skipped

---

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `src/demo_mode.py` | ~1126-1133 | Fix deadlock: move `_update_training_status()` outside lock |
| `src/tests/conftest.py` | ~184-201 | Add `requires_cassandra` and `requires_redis` skip handlers |
| `src/tests/conftest.py` | ~228-280 | Fix mock context manager and add side_effect functions |
