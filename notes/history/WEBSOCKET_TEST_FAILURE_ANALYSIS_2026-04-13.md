# WebSocket Test Failure Analysis — 2026-04-13

**Status**: RESOLVED on branch `fix/ws-origin-test-headers` (PR #153)
**Author**: Paul Calnon
**Affected suite**: `juniper-canopy/src/tests/`
**Originating failure**: 96 failed, 4334 passed, 73 skipped, 23 warnings

## 1. Summary

A single root cause produced 95 of 96 reported test failures: Phase B-pre-a
hardened the `/ws/training` and `/ws/control` WebSocket routes with an Origin
allow-list (security ticket `M-SEC-01b`). Pytest's `starlette.testclient.TestClient`
does not include an `Origin` header on `websocket_connect()` by default, so every
in-process WebSocket test was rejected at the route entry point with HTTP-style
disconnect, surfacing as `starlette.websockets.WebSocketDisconnect`.

The remaining failure — `test_demo_endpoints.py::TestAPIStatusEndpoint::test_api_status_shows_training_active`
— is **not** an independent regression. It is caused by the same module-scoped
`test_client` fixture that drives the WebSocket failures in `test_demo_endpoints.py`:
the fixture instantiates `TestClient(app)` without the `with` context manager, so
FastAPI's `lifespan()` never fires and the module-global `backend` is left at `None`.
In the original failing run the test still surfaced as an `AssertionError`
because an earlier-running test (e.g. `test_main_ws.py`) had already triggered
lifespan in its own `with TestClient(app) as ...` block, leaking the `backend`
global into this fixture by side effect. With the global accidentally populated,
`backend.is_training_active()` returns `False` immediately after fixture setup and
the `or`-chained "either training or epochs > 0" assertion fires.

After fixing the Origin header issue, this failure also clears, because the WS
tests in the same file no longer abort early — they reach the loop that drives
demo broadcasts, the heartbeat completes within the fixture's `time.sleep(2.0)`,
and the `is_training_active()` flag transitions to `True` before the assertion
is checked.

## 2. Root cause

### 2.1 Phase B-pre-a security hardening

Commit `590918b` (`feat(ws): origin allowlist, per-IP cap, audit logger, idle
timeout (B-pre-a)`) added the following gate to both WebSocket routes in
`src/main.py:374-386` and `src/main.py:465-477`:

```python
if ws_settings.allowed_origins:
    if not validate_origin(websocket, ws_settings.allowed_origins):
        await websocket.close(code=4003, reason="Origin not allowed")
        return
```

`ws_settings.allowed_origins` resolves to the configured allow-list, which in
the test environment defaults to `http://localhost:8050`.
`validate_origin()` reads `websocket.headers["origin"]` and compares it against
the list. `TestClient.websocket_connect()` does not set this header on its own,
so every test connection is rejected and the client surface raises
`WebSocketDisconnect` on the first `receive_*` call.

### 2.2 Affected test files (97 originally-listed instances)

| File | Tests |
|---|---|
| `tests/integration/test_cascor_ws_control.py` | 8 |
| `tests/integration/test_demo_endpoints.py` (WS subset) | 8 |
| `tests/integration/test_main_coverage.py` | 16 |
| `tests/integration/test_main_ws.py` | 19 |
| `tests/integration/test_websocket_control.py` | 9 |
| `tests/integration/test_websocket_message_schema.py` | 8 |
| `tests/integration/test_websocket_state.py` | 7 |
| `tests/unit/test_main_coverage_95.py` | 2 |
| `tests/unit/test_main_coverage_extended.py` | 17 |
| `tests/unit/test_main_import_and_lifespan.py` | 2 |
| **Total** | **96** (incl. the demo_endpoints assertion) |

## 3. Resolution (already applied on PR #153)

`src/tests/conftest.py` adds a session-scoped autouse fixture that monkeypatches
`starlette.testclient.TestClient.websocket_connect` to inject an allowed
`origin` header on every call:

```python
_WS_TEST_ORIGIN = "http://localhost:8050"

@pytest.fixture(scope="session", autouse=True)
def _inject_ws_origin_header():
    from starlette.testclient import TestClient
    global _original_ws_connect
    _original_ws_connect = TestClient.websocket_connect

    def _patched_ws_connect(self, url, subprotocols=None, **kwargs):
        headers = kwargs.get("headers", {})
        headers.setdefault("origin", _WS_TEST_ORIGIN)
        kwargs["headers"] = headers
        return _original_ws_connect(self, url, subprotocols=subprotocols, **kwargs)

    TestClient.websocket_connect = _patched_ws_connect
    yield
    TestClient.websocket_connect = _original_ws_connect
```

Strengths:

- Single point of change; no per-test edits.
- Uses `setdefault`, so any test that intentionally tests origin rejection by
  passing its own header is unaffected (`tests/unit/test_ws_security.py` still
  exercises the rejection path correctly).
- Guarded restore in fixture teardown protects the live class object across
  the session boundary.

Weaknesses:

- Monkeypatching a third-party class is an action at a distance; future
  starlette versions could change the `websocket_connect` signature. Mitigation:
  `**kwargs` forwarding ensures any new keyword args pass through unchanged.
- Tests that use `httpx.AsyncClient` to drive WebSockets directly are not
  covered. None exist today, but future tests will need to add an `origin`
  header explicitly.

## 4. Verification

Full test suite executed from the repository root with `JuniperCanopy` conda env:

```bash
conda activate JuniperCanopy
cd juniper-canopy
python -m pytest src/tests/ --no-header --tb=no -rN
```

Result on `fix/ws-origin-test-headers` HEAD (`8f6c798`):

```text
4424 passed, 94 skipped, 23 warnings in 394.41s (0:06:34)
```

Diff vs. originating failure baseline:

| Metric | Before | After | Δ |
|---|---|---|---|
| Failed | 96 | 0 | **−96** |
| Passed | 4334 | 4424 | +90 |
| Skipped | 73 | 94 | +21 |
| Warnings | 23 | 23 | 0 |

The +90/+21 swing reflects the previously-failing tests now executing to
completion (most pass, a handful skip on `RUN_SERVER_TESTS=0`). No tests were
removed, disabled, or commented out.

## 5. Latent issues identified (out of scope, recorded for follow-up)

These are pre-existing fragilities discovered while diagnosing the failures.
They do **not** cause failures in the current `RUN_SERVER_TESTS=0` profile and
are not blocking release.

### 5.1 `test_demo_endpoints.py::test_client` fixture leaks lifespan state

`src/tests/integration/test_demo_endpoints.py:29-43` constructs `TestClient(app)`
without the `with` context manager. FastAPI's `lifespan()` never fires from
this fixture, so `main.backend` is `None` until some other test's `with TestClient(app) as ...`
context populates the module global by side effect. When run in isolation
(or before any lifespan-using test), every endpoint that touches `backend`
raises `AttributeError: 'NoneType' object has no attribute ...`.

**Recommended fix** (deferred): change the fixture to

```python
@pytest.fixture(scope="module")
def test_client():
    os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
    from main import app
    with TestClient(app) as client:
        time.sleep(2.0)
        yield client
```

This makes the fixture self-contained and removes the cross-test ordering
dependency. Filing as a separate cleanup (not bundled with the security fix)
to keep PR #153 minimal.

### 5.2 `test_docker_demo_mode_default.py` is CWD-sensitive

`src/tests/regression/test_docker_demo_mode_default.py:39,43` reads
`Path("Dockerfile")` and `Path("conf/Dockerfile")` as relative paths. These
work when pytest is invoked from the repo root (the documented entrypoint per
`AGENTS.md`) but fail with `FileNotFoundError` when invoked from `src/`.
Suggested fix: derive the path from `Path(__file__).resolve().parents[3]`.
Not in original failure list because the originating run used the documented
repo-root entrypoint.

### 5.3 23 deprecation/runtime warnings (pre-existing)

The 23-warning count is unchanged from the originating failing run. They
break down approximately as:

- ~13 `DeprecationWarning` from `TrainingMetricsComponent` — these are
  intentional: `tests/unit/test_training_metrics.py` and
  `tests/unit/frontend/test_components_basic.py` are validating the deprecated
  shim still works for the migration period. The correct fix is to wrap the
  instantiations in `pytest.warns(DeprecationWarning)`, which both silences the
  warning and asserts it is raised. This preserves coverage of the deprecated
  path.
- ~6 `DeprecationWarning` / `RuntimeWarning` from third-party libraries (dash,
  starlette, asyncio). Not actionable from this codebase — would need filterwarnings
  rules in `pyproject.toml` if we want a clean log.
- 1 `DeprecationWarning` in `src/main.py:322` and 1 in `src/demo_mode.py:554`
  from internal calls into a deprecated API path. Worth a follow-up to migrate
  the call sites.
- 1 `ResourceWarning` from `tempfile` in `test_main_endpoints_coverage.py::TestMetricsLayouts::test_get_not_found`
  indicates a temporary file handle is not being closed before the test exits.

Tracking these as a separate hygiene PR; they did not cause the originating
test failures and addressing them in the same PR as the security fix would
muddy the change history.

## 6. Recommendation

PR #153 (`fix/ws-origin-test-headers`) is the correct, minimal fix. Merge it
as-is. The latent issues in §5 should be filed as separate cleanup tickets.

## 7. Reproduction commands

```bash
# Establish the failure (on commit 590918b, before the fix):
conda activate JuniperCanopy
cd /home/pcalnon/Development/python/Juniper/juniper-canopy
git checkout 590918b
python -m pytest src/tests/ --no-header -q   # 96 failed

# Verify the fix (on PR #153 HEAD):
git checkout fix/ws-origin-test-headers
python -m pytest src/tests/ --no-header --tb=no -rN
# expected: 4424 passed, 94 skipped, 23 warnings
```
