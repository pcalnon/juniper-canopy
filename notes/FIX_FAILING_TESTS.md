# Fix Failing Tests - Analysis and Remediation Plan

**Last Updated:** 2026-02-04
**Version:** 1.2.0
**Status:** COMPLETE - All fixes applied and verified (Round 2 included)
**Branch:** subproject.juniper_canopy.integration_and_enhancements

## Table of Contents

- [Executive Summary](#executive-summary)
- [Test Results Overview](#test-results-overview)
- [Priority Matrix](#priority-matrix)
- [Issue 1: Missing pytest-mock Dependency (54 ERROR Tests)](#issue-1-missing-pytest-mock-dependency-54-error-tests)
- [Issue 2: Snapshot Private Attribute Leakage (1 FAILED Test)](#issue-2-snapshot-private-attribute-leakage-1-failed-test)
- [Issue 3: WebSocket Control Command Race Condition (1 FAILED Test)](#issue-3-websocket-control-command-race-condition-1-failed-test)
- [Issue 4: Server-Dependent Tests Without Running Server (8 FAILED Tests)](#issue-4-server-dependent-tests-without-running-server-8-failed-tests)
- [Issue 5: Logger VERBOSE Level Not Registered (2 XFAIL Tests)](#issue-5-logger-verbose-level-not-registered-2-xfail-tests)
- [Issue 6: LoggingConfig Empty YAML Handling (1 XFAIL Test)](#issue-6-loggingconfig-empty-yaml-handling-1-xfail-test)
- [Remediation Summary](#remediation-summary)

---

## Executive Summary

Analysis of the full test suite (3,252 tests total) identified **67 non-passing tests** across 6 distinct root causes:

| Status  | Count | Root Causes |
|---------|-------|-------------|
| ERROR   | 54    | 1 (missing pytest-mock dependency) |
| FAILED  | 10    | 3 (source code bug, race condition, missing server) |
| XFAIL   | 3     | 2 (missing log level, empty YAML handling) |
| WARNING | 1     | (standard pytest deprecation - not actionable) |

**Critical finding:** 54 of the 67 non-passing tests (81%) share a single root cause: the `pytest-mock` package is not installed in the current environment. Installing it would immediately resolve all 54 ERROR tests.

---

## Test Results Overview

```
Total Tests:    3,252
Passed:         3,151  (96.9%)
Failed:            10  (0.3%)
Errors:            54  (1.7%)
Skipped:           34  (1.0%)
XFail:              3  (0.1%)
Duration:       294.63s
```

### Non-Passing Tests by Category

#### ERROR (54 tests) - Fixture Resolution Failure

All 54 ERROR tests use the `mocker` fixture from `pytest-mock`:

- `test_dashboard_manager.py::TestDashboardManagerHandlersWithMocking` (17 tests)
- `test_dashboard_manager.py::TestTrainingButtonHandlers` (3 tests)
- `test_dashboard_manager.py::TestParameterHandlers` (5 tests)
- `test_dashboard_manager.py::TestHandleTrainingButtons` (3 tests)
- `test_dashboard_manager.py::TestDashboardManagerMiscMethods` (4 tests)
- `test_dashboard_manager_95.py::TestInitAppliedParamsNon200` (2 tests)
- `test_dashboard_manager_95.py::TestTrainingButtonsDebounce` (2 tests)
- `test_dashboard_manager_95.py::TestAllButtonHandlerSuccessCases` (3 tests)
- `test_dashboard_manager_95.py::TestCallbackHandlerReturns` (8 tests)
- `test_dashboard_manager_95.py::TestSyncBackendParamsHandler` (1 test)
- `test_dashboard_manager_95.py::TestApplyParametersHandler` (1 test)
- `test_dashboard_manager_95.py::TestAdditionalHandlerCases` (5 tests)

#### FAILED (10 tests) - Source Code and Environment Issues

| Test | Error Type | Category |
|------|-----------|----------|
| `test_demo_endpoints.py::test_training_websocket_receives_state_messages` | AssertionError: No state messages | Server-dependent |
| `test_demo_endpoints.py::test_training_websocket_receives_metrics_messages` | AssertionError: No metrics messages | Server-dependent |
| `test_demo_endpoints.py::test_demo_mode_broadcasts_data` | AssertionError: No messages received | Server-dependent |
| `test_parameter_persistence.py::test_api_set_params_integration` | httpx.ConnectError | Server-dependent |
| `test_candidate_visibility.py::test_server_health` | requests.ConnectionError | Server-dependent |
| `test_candidate_visibility.py::test_state_endpoint_returns_data` | requests.ConnectionError | Server-dependent |
| `test_candidate_visibility.py::test_candidate_pool_becomes_active` | requests.ConnectionError | Server-dependent |
| `test_candidate_visibility.py::test_pool_metrics_available_when_active` | requests.ConnectionError | Server-dependent |
| `test_main_coverage_extended.py::test_control_command_sequence` | AssertionError: 'ok' not in response | Race condition |
| `test_main_snapshot_coverage.py::test_create_snapshot_stores_training_state` | AssertionError: '_private' in attrs | Source code bug |

#### XFAIL (3 tests) - Known Bugs

| Test | Reason |
|------|--------|
| `test_logger_coverage_95.py::test_verbose_logging` | `logging.VERBOSE` attribute doesn't exist |
| `test_logger_coverage_95.py::test_verbose_with_context` | `logging.VERBOSE` attribute doesn't exist |
| `test_logger_coverage_95.py::test_empty_yaml_file` | `LoggingConfig` doesn't handle empty YAML |

---

## Priority Matrix

Issues are prioritized by: severity of failure, importance of component, potential for software defects, and development impact.

| Priority | Issue | Impact | Effort | Tests Affected |
|----------|-------|--------|--------|----------------|
| **P0 - Critical** | Missing pytest-mock dependency | Blocks 54 tests from running; zero coverage of dashboard handler logic | Trivial (pip install) | 54 |
| **P1 - High** | Snapshot private attribute leakage | Security/data integrity bug in production code; private state stored in HDF5 files | Low (add filter) | 1 |
| **P2 - Medium** | WebSocket control race condition | Intermittent test failure; masks real regressions | Medium (fix test or source) | 1 |
| **P3 - Low** | Server-dependent tests run without server | Tests correctly marked; environmental configuration issue | None (documentation) | 8 |
| **P4 - Low** | Logger VERBOSE level not registered | Logger feature incomplete; tests correctly marked xfail | Low (register level attribute) | 2 |
| **P5 - Low** | LoggingConfig empty YAML handling | Edge case; test correctly marked xfail | Low (null check) | 1 |

---

## Issue 1: Missing pytest-mock Dependency (54 ERROR Tests)

### Status: ERROR (54 tests)
### Priority: P0 - Critical
### Severity: Blocks test execution for all dashboard handler tests

### Affected Tests

All tests in:
- `src/tests/unit/frontend/test_dashboard_manager.py` (classes: `TestDashboardManagerHandlersWithMocking`, `TestTrainingButtonHandlers`, `TestParameterHandlers`, `TestHandleTrainingButtons`, `TestDashboardManagerMiscMethods`)
- `src/tests/unit/frontend/test_dashboard_manager_95.py` (classes: `TestInitAppliedParamsNon200`, `TestTrainingButtonsDebounce`, `TestAllButtonHandlerSuccessCases`, `TestCallbackHandlerReturns`, `TestSyncBackendParamsHandler`, `TestApplyParametersHandler`, `TestAdditionalHandlerCases`)

### Root Cause

The `pytest-mock` package is **not installed** in the current Python environment despite being listed in:
- `conf/requirements.txt` (`pytest-mock==3.15.1`)
- `conf/requirements_ci.txt` (`pytest-mock>=3.12`)
- `conf/conda_environment.yaml` (`pytest-mock>=3.12`)

**Verification:**
```bash
$ python -c "import pytest_mock"
ModuleNotFoundError: No module named 'pytest_mock'
```

All 54 tests use the `mocker` fixture, which is provided by `pytest-mock`. When the package is missing, pytest cannot resolve the fixture and reports ERROR during test collection/setup.

### Impact

- **Zero test coverage** for all dashboard callback handler methods
- These handlers include: metrics store updates, topology updates, dataset updates, boundary updates, network info, training buttons, parameter application, and status bar updates
- Any regressions in dashboard handler logic are completely undetectable

### Historical Context

This exact issue was identified and resolved on 2026-01-12 (see `notes/VALIDATION_REPORT_2026-01-12.md`). The environment was likely recreated without installing `pytest-mock`, or the package was removed during a dependency update.

### Proposed Fix

**Immediate fix:**
```bash
pip install pytest-mock>=3.12
```

**Permanent fix:** Ensure `pytest-mock` is installed whenever the environment is created or updated. It is already listed in the dependency files, so the issue is purely an environment synchronization problem.

### Files to Modify

None - this is an environment issue, not a code issue.

---

## Issue 2: Snapshot Private Attribute Leakage (1 FAILED Test)

### Status: FAILED
### Priority: P1 - High
### Severity: Source code bug affecting data integrity and potential security

### Affected Test

`src/tests/unit/test_main_snapshot_coverage.py::TestCreateSnapshotWithTrainingState::test_create_snapshot_stores_training_state`

### Error Message

```
assert '_private' not in <Attributes of HDF5 object at 135852546231968>
```

### Root Cause

In `src/main.py:1151-1155`, the HDF5 snapshot creation iterates over **all** attributes of the training state object without filtering private/protected attributes:

```python
# src/main.py lines 1151-1155
if training_state:
    state_group = f.create_group("training_state")
    for key, value in training_state.__dict__.items():
        if isinstance(value, (int, float, str, bool)):
            state_group.attrs[key] = value
```

The code stores every attribute from `training_state.__dict__` that has a serializable type, including attributes prefixed with `_` (private/protected). The test creates a `MockTrainingState` with `self._private = "should_be_ignored"` and correctly expects it to be excluded, but the source code has no filter.

### Impact

- **Data integrity**: Internal implementation details leak into persistent HDF5 snapshots
- **Security**: Private state attributes (potentially containing sensitive data) are stored in snapshot files
- **Compatibility**: Future changes to private attributes could break snapshot restore operations
- **Convention violation**: Python convention is that `_`-prefixed attributes are implementation details

### Proposed Fix

**Fix in `src/main.py`** - Add a filter to exclude private/protected attributes:

```python
# src/main.py line 1153 - change from:
for key, value in training_state.__dict__.items():
    if isinstance(value, (int, float, str, bool)):
        state_group.attrs[key] = value

# To:
for key, value in training_state.__dict__.items():
    if not key.startswith("_") and isinstance(value, (int, float, str, bool)):
        state_group.attrs[key] = value
```

### Files to Modify

- `src/main.py` (line 1153-1155) - Add `not key.startswith("_")` filter

---

## Issue 3: WebSocket Control Command Race Condition (1 FAILED Test)

### Status: FAILED (intermittent)
### Priority: P2 - Medium
### Severity: Flaky test that masks real regressions

### Affected Test

`src/tests/unit/test_main_coverage_extended.py::TestControlWebSocketBranches::test_control_command_sequence`

### Error Message

```
assert ('ok' in {'data': {'epoch': 1, 'metrics': {'accuracy': 0.5230504803625288, 'loss': 0.94524787551855, 'val_accuracy': 0.4926881115361997, 'val_loss': 1.0437171844941882}, 'network_topology': {'hid...
```

### Root Cause

This is a **race condition** between the control response and training broadcast messages:

1. Test sends `{"command": "start"}` to `/ws/control`
2. The control handler calls `demo_mode_instance.start()` which launches a background training thread
3. The training thread immediately begins broadcasting metrics via `websocket_manager.broadcast_from_thread()`
4. The control handler then sends a personal response `{"ok": True, ...}` via `send_personal_message()`
5. The control WebSocket client receives **both** broadcast messages and personal messages
6. `ws.receive_json()` returns whichever message arrives first

When the training thread broadcasts before the personal response is sent, the test receives a metrics broadcast message (containing `data.epoch`, `data.metrics`, etc.) instead of the expected control response (containing `ok: True`).

**Reproduction:** The test passes consistently in isolation (5/5 runs) but fails intermittently under load (e.g., during full suite execution) when the system is slower and the training thread gets scheduled before the response is sent.

### Test Code (lines 1073-1080)

```python
def test_control_command_sequence(self, app_client):
    with app_client.websocket_connect("/ws/control") as ws:
        ws.receive_json()  # connection_established
        ws.send_json({"command": "start"})
        response = ws.receive_json()
        assert "ok" in response or "state" in response
```

### Impact

- Intermittent CI failures reduce confidence in test suite reliability
- Other developers may dismiss real failures as "just that flaky test"
- The test provides no reliable coverage of the control command flow

### Proposed Fix

**Option A (Recommended): Fix the test to handle the race condition**

Consume messages in a loop until the control response is found or timeout:

```python
def test_control_command_sequence(self, app_client):
    with app_client.websocket_connect("/ws/control") as ws:
        ws.receive_json()  # connection_established
        ws.send_json({"command": "start"})

        # Consume messages until we find the control response
        control_response = None
        for _ in range(10):  # Max 10 messages
            response = ws.receive_json()
            if "ok" in response:
                control_response = response
                break

        assert control_response is not None, "Control response not received"
        assert control_response["ok"] is True
```

**Option B: Fix the source code to exclude control clients from broadcasts**

Add an `exclude` parameter to `broadcast` calls in the demo mode training loop, excluding control WebSocket clients. This is a larger change and may not be desirable since control clients may legitimately want to receive training updates.

**Option C: Send personal response before starting the training thread**

Reorder the control handler to send the response before calling `demo_mode_instance.start()`:

```python
# In websocket_control_endpoint, for the "start" command:
response = {"ok": True, "command": command}
await websocket_manager.send_personal_message(response, websocket)
state = demo_mode_instance.start(reset=reset)  # Start after response sent
```

### Files to Modify

- **Option A**: `src/tests/unit/test_main_coverage_extended.py` (line 1073-1080)
- **Option B**: `src/main.py` and `src/communication/websocket_manager.py`
- **Option C**: `src/main.py` (lines 402-406 in `websocket_control_endpoint`)

---

## Issue 4: Server-Dependent Tests Without Running Server (8 FAILED Tests)

### Status: FAILED
### Priority: P3 - Low
### Severity: Environmental/configuration issue, not a code defect

### Affected Tests

**WebSocket broadcast tests (3 tests):**
- `test_demo_endpoints.py::TestWebSocketTrainingEndpoint::test_training_websocket_receives_state_messages`
- `test_demo_endpoints.py::TestWebSocketTrainingEndpoint::test_training_websocket_receives_metrics_messages`
- `test_demo_endpoints.py::TestDataFlowIntegration::test_demo_mode_broadcasts_data`

**HTTP connection tests (5 tests):**
- `test_parameter_persistence.py::test_api_set_params_integration`
- `test_candidate_visibility.py::TestCandidateVisibility::test_server_health`
- `test_candidate_visibility.py::TestCandidateVisibility::test_state_endpoint_returns_data`
- `test_candidate_visibility.py::TestCandidateVisibility::test_candidate_pool_becomes_active`
- `test_candidate_visibility.py::TestCandidateVisibility::test_pool_metrics_available_when_active`

### Root Cause

All 8 tests require a live running server at `localhost:8050` and are correctly marked with `@pytest.mark.requires_server`. The `conftest.py` skip logic properly skips these when `RUN_SERVER_TESTS` is not set:

```python
# src/tests/conftest.py - pytest_collection_modifyitems
if not os.getenv("RUN_SERVER_TESTS"):
    # Skip tests with requires_server marker
```

**Verified:** When `RUN_SERVER_TESTS` is not set, all 8 tests are skipped:
```
SKIPPED [4] - Server tests disabled (set RUN_SERVER_TESTS=1)
```

The failures occur only when `RUN_SERVER_TESTS=1` is set in the environment but no server is actually running. This is a user/CI configuration issue.

### WebSocket broadcast failures (tests 1-3)

These tests cannot work under `TestClient` even with the server running in-process because:
- `broadcast_from_thread()` uses `asyncio.run_coroutine_threadsafe()` to schedule broadcasts
- The TestClient's event loop is synchronously blocked in the WebSocket receive handler
- The broadcast coroutine never gets a chance to execute
- These tests inherently require a separate server process

### HTTP connection failures (tests 4-8)

These tests use raw `httpx.AsyncClient()` or `requests.get()` to connect to `http://localhost:8050`. They require an actual server process running.

### Impact

- No code defect exists
- Skip logic works correctly
- Failures only occur with improper environment configuration

### Proposed Fix

**No code changes required.** The test markers and skip logic are correct.

**Documentation fix:** Add a note to the test run instructions clarifying that `RUN_SERVER_TESTS=1` requires an actual running server:

```bash
# To run server-dependent tests:
# 1. Start the server in one terminal:
./demo
# 2. In another terminal, run the tests:
export RUN_SERVER_TESTS=1
cd src && pytest -m requires_server -v
```

### Files to Modify

None (documentation-only update in CLAUDE.md).

---

## Issue 5: Logger VERBOSE Level Not Registered (2 XFAIL Tests)

### Status: XFAIL
### Priority: P4 - Low
### Severity: Incomplete feature implementation in logger module

### Affected Tests

- `test_logger_coverage_95.py::TestVerboseLogging::test_verbose_logging`
- `test_logger_coverage_95.py::TestVerboseLogging::test_verbose_with_context`

### Root Cause

The `CascorLogger` class registers custom log level **names** via `logging.addLevelName()` but does not register the corresponding **attributes** on the `logging` module:

```python
# src/logger/logger.py lines 192-200
class CascorLogger:
    VERBOSE_LEVEL = 5

    def __init__(self, ...):
        logging.addLevelName(self.VERBOSE_LEVEL, "VERBOSE")  # Registers name only
        # Does NOT set logging.VERBOSE = 5
```

The `verbose()` method at line 307 calls `self._log_with_context(logging.VERBOSE, ...)`, but `logging.VERBOSE` doesn't exist as an attribute, causing `AttributeError`.

Contrast with the `trace()` method at line 311 which correctly uses `self.TRACE_LEVEL` (the class attribute) instead of `logging.TRACE`.

### Impact

- The `CascorLogger.verbose()` method raises `AttributeError` when called
- Any code calling `logger.verbose(...)` will crash
- The `fatal()` method works only because Python's `logging.FATAL` happens to already exist (it's an alias for `logging.CRITICAL`)

### Proposed Fix

**Option A (Recommended): Use the class constant in `verbose()` method, matching `trace()`:**

```python
# src/logger/logger.py line 307 - change from:
def verbose(self, message: str, **kwargs):
    self._log_with_context(logging.VERBOSE, message, **kwargs)

# To:
def verbose(self, message: str, **kwargs):
    self._log_with_context(self.VERBOSE_LEVEL, message, **kwargs)
```

**Option B: Register the attribute on the logging module:**

```python
# In CascorLogger.__init__, add:
if not hasattr(logging, 'VERBOSE'):
    logging.VERBOSE = self.VERBOSE_LEVEL
```

Option A is preferred because it follows the existing pattern used by `trace()` and doesn't modify the global `logging` module.

### Files to Modify

- `src/logger/logger.py` (line 307) - Change `logging.VERBOSE` to `self.VERBOSE_LEVEL`
- `src/tests/unit/test_logger_coverage_95.py` - Remove `xfail` marker from affected tests

---

## Issue 6: LoggingConfig Empty YAML Handling (1 XFAIL Test)

### Status: XFAIL
### Priority: P5 - Low
### Severity: Edge case in configuration loading

### Affected Test

- `test_logger_coverage_95.py::TestLoggingConfigLoadBranches::test_empty_yaml_file`

### Root Cause

`LoggingConfig._load_config()` in `src/logger/logger.py` does not handle the case where `yaml.safe_load()` returns `None` for an empty YAML file:

```python
# src/logger/logger.py lines 488-507
def _load_config(self) -> Dict:
    if not os.path.exists(self.config_path):
        return self._get_default_config()

    try:
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)  # Returns None for empty file
    except Exception:
        return self._get_default_config()

    # BUG: config is None here for empty files
    if "logging" in config:  # TypeError: argument of type 'NoneType' is not iterable
        ...
```

When the YAML file exists but is empty, `yaml.safe_load()` returns `None` (not an empty dict). The code catches `Exception` from `yaml.safe_load()` but `None` is a valid return, not an exception. The subsequent `if "logging" in config:` check then raises `TypeError` because `None` is not iterable.

### Impact

- If an empty `logging_config.yaml` file exists, the application will crash during logger initialization
- Edge case unlikely in production but represents a defensive programming gap

### Proposed Fix

Add a null check after `yaml.safe_load()`:

```python
# src/logger/logger.py - after line 496
config = yaml.safe_load(f)
if not config:  # Handle empty file (None) or empty document ({})
    return self._get_default_config()
```

### Files to Modify

- `src/logger/logger.py` (after line 496) - Add null/empty check
- `src/tests/unit/test_logger_coverage_95.py` - Remove `xfail` marker from affected test

---

## Remediation Summary

### All Fixes Applied and Verified

| Priority | Action | Status | Files Modified |
|----------|--------|--------|----------------|
| P0 | Installed `pytest-mock>=3.12` | DONE | Environment only |
| P1 | Added `not key.startswith("_")` filter in snapshot creation | DONE | `src/main.py` |
| P2 | Fixed test to drain broadcast messages before asserting | DONE | `src/tests/unit/test_main_coverage_extended.py` |
| P3 | Server-dependent tests (no code change needed) | N/A | Already correctly marked |
| P4 | Changed `logging.VERBOSE` to `self.VERBOSE_LEVEL` | DONE | `src/logger/logger.py` |
| P5 | Added null check after `yaml.safe_load()` | DONE | `src/logger/logger.py` |
| - | Removed 3 `@pytest.mark.xfail` markers | DONE | `src/tests/unit/test_logger_coverage_95.py` |

### Verified Results (Round 1)

```
Before: 3,151 passed, 10 failed, 54 errors, 3 xfailed, 34 skipped, 1 warning (294.63s)
After:  3,207 passed, 0 failed, 0 errors, 0 xfailed, 45 skipped, 1 warning (145.25s)

Net change: +56 passing, -10 failed, -54 errors, -3 xfailed
```

---

## Round 2 Fixes

Additional test failures found after further environment updates (h5py installed, skip markers removed).

### Issue 7: WebSocket State Tests Skipping (5 Tests)

**Root Cause:** Tests waited for `broadcast_from_thread()` state messages that can't be delivered through TestClient's threading model. Tests used `pytest.skip("No state messages received")` as fallback.

**Fix:**
1. Added `{"type": "state", ...}` personal message sent on `/ws/training` connect in `main.py` handler
2. State data uses `training_state.get_state()` for standardized field format
3. Rewrote `test_websocket_state.py` to consume deterministic connect sequence (connection_established → initial_status → state)
4. Removed `@pytest.mark.requires_server` since tests now work with TestClient
5. Removed all `try/except: pytest.skip()` patterns
6. Used case-insensitive comparison for status/phase values (title case vs uppercase from TrainingStateMachine enum)

**Files:** `src/main.py`, `src/tests/integration/test_websocket_state.py`

### Issue 8: WebSocket Ping-Pong Tests Broken (2 Tests)

**Root Cause:** Adding the state message on connect created a 3-message connect sequence instead of 2. Tests that drained only 2 messages before sending ping received the state message instead of pong.

**Fix:** Added third `receive_json()` call to drain the state message before sending ping.

**Files:** `src/tests/integration/test_main_coverage.py`, `src/tests/integration/test_main_ws.py`

### Issue 9: Logger Coverage Skip Marker (1 Test)

**Root Cause:** `test_verbose_logging` had `@pytest.mark.skip` because VERBOSE was not a standard logging level.

**Fix:** Removed skip marker (VERBOSE level works after P4 fix from Round 1).

**Files:** `src/tests/unit/test_logger_coverage.py`

### Issue 10: WebSocket Control Race Condition (1 Test)

**Root Cause:** Same race condition as P2 - `test_unknown_command_returns_error` received broadcast instead of control response.

**Fix:** Added message-draining loop pattern (same as P2).

**Files:** `src/tests/unit/test_main_coverage_extended.py`

### Issue 11: DemoMode Singleton State Pollution

**Root Cause:** `reset_singletons` fixture reset `DemoMode._instance` but not the module-level `_demo_instance` used by `get_demo_mode()`. Stale state from earlier tests persisted.

**Fix:** Extended `reset_singletons` to also reset `demo_mode._demo_instance`.

**Files:** `src/tests/conftest.py`

### Round 2 Remediation Summary

| Issue | Action | Status | Files Modified |
|-------|--------|--------|----------------|
| #7 | State message on WS connect + test rewrite | DONE | `src/main.py`, `src/tests/integration/test_websocket_state.py` |
| #8 | Drain 3rd connect message in ping-pong tests | DONE | `src/tests/integration/test_main_coverage.py`, `test_main_ws.py` |
| #9 | Remove skip marker from test_verbose_logging | DONE | `src/tests/unit/test_logger_coverage.py` |
| #10 | Message-draining loop for unknown command test | DONE | `src/tests/unit/test_main_coverage_extended.py` |
| #11 | Reset `_demo_instance` in `reset_singletons` | DONE | `src/tests/conftest.py` |

### Verified Results (Round 2)

```
Final: 3,215 passed, 0 failed, 0 errors, 0 xfailed, 37 skipped (123.90s)

All 37 skips are legitimate:
- 18 CasCor backend not available
- 8 Server tests disabled
- 4 Requires running server
- 2 CORS middleware not visible via TestClient
- 2 HDF5 patching limitations
- 1 CUDA not available
- 2 Server not running
```
