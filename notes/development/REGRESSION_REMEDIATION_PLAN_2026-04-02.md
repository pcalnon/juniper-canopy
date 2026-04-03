# Juniper Project: Regression Remediation Plan

**Date**: 2026-04-02
**Companion**: REGRESSION_ANALYSIS_2026-04-02.md
**Status**: Active

---

## Phase 1: Critical — CasCor Training Failure (P0)

### 1.1 Fix Walrus Operator Precedence Bug (RC-CASCOR-001)

**File**: `src/cascade_correlation/cascade_correlation.py:1708`

**Current**:

```python
if snapshot_path := self.create_snapshot() is not None:
```

**Fix**:

```python
if (snapshot_path := self.create_snapshot()) is not None:
```

**Risk**: None — pure precedence correction.
**Testing**: Unit test with mock `create_snapshot()` returning a path string; verify `snapshot_path` receives the string, not a boolean.

---

### 1.2 Fix WebSocket Coroutine Leak (RC-CASCOR-002)

**File**: `src/api/websocket/manager.py:89-101`

**Approach A (Recommended): Catch all exceptions:**

```python
def broadcast_from_thread(self, message: dict) -> None:
    if self._event_loop is None or self._event_loop.is_closed():
        return
    coro = self.broadcast(message)
    try:
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)
    except Exception:
        coro.close()
        logger.debug("Cannot broadcast: event loop unavailable or closed")
```

**Strengths**: Catches all exception types. Guarantees coroutine cleanup.
**Weaknesses**: Broad except may hide unexpected exceptions.
**Guardrail**: Debug log always records the failure.

**Approach B: Explicit exception list + finally:**

```python
def broadcast_from_thread(self, message: dict) -> None:
    if self._event_loop is None or self._event_loop.is_closed():
        return
    coro = self.broadcast(message)
    try:
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)
    except (RuntimeError, ValueError, TypeError) as e:
        logger.debug(f"Cannot broadcast: {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected broadcast error: {type(e).__name__}: {e}")
    finally:
        # Coroutine cleanup is handled by run_coroutine_threadsafe on success
        # On failure, we close manually
        pass
```

**Strengths**: Distinguishes expected from unexpected failures.
**Weaknesses**: May miss new exception types. More complex.

**Recommendation**: Approach A — simpler, safer, no missing exception types.

---

### 1.3 Fix Exception Propagation in _run_training (RC-CASCOR-003)

**File**: `src/api/lifecycle/manager.py:533-538`

**Current**:

```python
except Exception as e:
    self.logger.error(f"Training failed: {e}", exc_info=True)
```

**Fix**:

```python
except Exception as e:
    self.logger.error(f"Training failed: {e}", exc_info=True)
    self._training_state = "failed"
    self._training_error = str(e)
    # Broadcast failure to WebSocket clients
    try:
        self._ws_manager.broadcast_from_thread({
            "type": "training_failed",
            "data": {"error": str(e), "phase": self._current_phase}
        })
    except Exception:
        pass  # Best-effort notification
```

**Risk**: Low — adds state update and best-effort notification.
**Testing**: Unit test verifying state transitions to "failed" on exception. Integration test verifying WebSocket receives failure event.

---

### 1.4 Fix Drain Thread Queue Timing (RC-CASCOR-004)

**File**: `src/api/lifecycle/manager.py:383-401`

**Fix**: Add a guard in the drain thread that waits for the queue to be initialized before polling:

```python
def _drain_progress_queue(self, stop_event, network):
    """Drain progress queue with initialization guard."""
    queue = None
    while not stop_event.is_set():
        if queue is None:
            queue = getattr(network, '_persistent_progress_queue', None)
            if queue is None:
                stop_event.wait(timeout=0.5)
                continue
        try:
            item = queue.get_nowait()
            self._process_progress_item(item)
        except Empty:
            stop_event.wait(timeout=0.1)
```

**Risk**: Low — adds graceful initialization wait.
**Testing**: Unit test with delayed queue creation; verify no crash.

---

### 1.5 Fix SharedMemory Lifecycle (RC-CASCOR-005)

**File**: `src/cascade_correlation/cascade_correlation.py:1825-1848`

**Fix**: Add atomic cleanup guard:

```python
try:
    shm = SharedTrainingMemory(
        tensors=[candidate_input, y, residual_error],
        name_suffix=str(uuid.uuid4())[:8],
    )
    self._active_shm_blocks.append(shm)
    shm_metadata = shm.get_metadata()
    # ... metadata updates ...
except Exception as shm_err:
    # Clean up partially-created block
    if 'shm' in locals() and shm in self._active_shm_blocks:
        self._active_shm_blocks.remove(shm)
        try:
            shm.close_and_unlink()
        except Exception:
            pass
    self.logger.warning(f"OPT-5 SharedMemory creation failed: {shm_err}")
    # Fall back to full tasks
    training_inputs = (candidate_input, self.candidate_epochs, ...)
```

**Risk**: Medium — cleanup during exception may itself fail.
**Guardrail**: Inner try/except prevents cleanup failure from masking original error.

---

### 1.6 Remove Undeclared Global Variable (RC-CASCOR-006)

**File**: `src/cascade_correlation/cascade_correlation.py:2923`

**Fix**: Remove `global shared_object_dict` line.

**Risk**: None — dead code removal.

---

### 1.7 Extract ActivationWithDerivative to Shared Module (RC-CASCOR-007)

**Approach A (Recommended): Extract to shared utils module:**

Create `src/utils/activation.py` with the canonical `ActivationWithDerivative` class and `ACTIVATION_MAP`. Update both `cascade_correlation.py` and `candidate_unit.py` to import from the shared module.

**Approach B: Keep in cascade_correlation.py, import from there:**

Have `candidate_unit.py` import from `cascade_correlation.py`. This creates a dependency direction that may cause circular imports.

**Recommendation**: Approach A — clean separation, no circular import risk.

---

## Phase 2: Critical — Canopy-CasCor Connection (P0)

### 2.1 Fix Response Key Mismatch in CasCor Client

**File**: `juniper-cascor-client/juniper_cascor_client/client.py:76`

**Current**:

```python
result.get("data", {}).get("network_loaded")
```

**Fix**:

```python
result.get("details", {}).get("network_loaded")
```

**Risk**: None — aligns with actual server response format.
**Testing**: Unit test with mock server response using "details" key.

### 2.2 Fix Connection Gate in Service Adapter

**File**: `juniper-canopy/src/backend/cascor_service_adapter.py:122-128`

**Current**: Uses `is_ready()` which requires `network_loaded=True`
**Fix**: Use `is_alive()` which only requires HTTP 200 from health endpoint

**Risk**: Low — `is_alive()` is less restrictive, which is appropriate for initial connection.

---

## Phase 3: High — Canopy UI Fixes (P1)

### 3.1 Fix Tab Ordering

**File**: `src/frontend/dashboard_manager.py:1075-1134`

Reorder tab definitions to match expected order. Current order appears correct based on code analysis. Verify at runtime.

### 3.2 Fix Network Topology Output Nodes

**File**: `src/frontend/components/network_visualizer.py`

Investigate `_build_network_graph()` for duplicate output node creation. Ensure topology data deduplicates nodes by ID before rendering.

### 3.3 Fix Convergence Threshold Display

Trace the field mapping from cascor's status endpoint through to the sidebar input binding. Fix any key misalignment.

### 3.4 Fix Cassandra Panel API URL

**File**: `src/frontend/components/cassandra_panel.py:99-120`

**Fix**: Replace Flask request context dependency with settings-based URL construction:

```python
def _api_url(self, path: str) -> str:
    from urllib.parse import urljoin
    origin = f"http://127.0.0.1:{self._settings.server.port}"
    return urljoin(f"{origin}/", path.lstrip("/"))
```

### 3.5 Fix Decision Boundary Aspect Ratio

**File**: `src/frontend/components/decision_boundary.py:150`

Add Plotly layout constraint for equal aspect ratio:

```python
layout=dict(
    yaxis=dict(scaleanchor="x", scaleratio=1),
    height=600,
)
```

And update container style to use `aspect-ratio`:

```python
style={"width": "100%", "aspectRatio": "1 / 1", "maxHeight": "800px"}
```

### 3.6 Fix Dataset View Aspect Ratio

Same approach as 3.5 for `dataset_plotter.py`.

### 3.7 Populate Dataset Dropdown

Implement callback to query juniper-data for available generators and populate the dropdown. Pre-select the current training dataset.

### 3.8 Dynamic Dataset Parameters Section

Replace hardcoded "Spiral Dataset" section with dynamic "Current Dataset" section that changes fields based on selected dataset type.

### 3.9 Implement Generate Dataset Behavior

Implement full workflow: stop training → generate dataset → display → check compatibility → prompt user or restart.

### 3.10 Move Snapshots Refresh Button

Move refresh button and status message from main panel header to "Available Snapshots" section heading.

### 3.11 Add Decision Boundary Replay

Implement history store for decision boundary visualizations at each hidden node addition. Add replay controls.

---

## Phase 4: Medium — Dark Mode Fixes (P2)

### 4.1 Fix Candidate Loss Graph Background

**File**: `candidate_metrics_panel.py`

Set graph figure layout:

```python
figure.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
```

And add dark mode font color toggle.

### 4.2 Fix Parameters Tab Table Background

Ensure `dbc.Table` components don't override dark mode CSS. Add explicit dark mode classes or remove inline background styles.

### 4.3 Fix Tutorial Tab Table Background

Same approach as 4.2.

---

## Phase 5: Low — Code Quality (P3)

### 5.1 Remove Misleading Import Alias

Remove `import datetime as pd` from `cascade_correlation.py:39`.

### 5.2 Remove Duplicate Snapshot Counter Init

Remove second `self.snapshot_counter = 0` at line 779.

### 5.3 Add SharedMemory Cleanup Guard

Add try/finally in SharedMemory creation to clean up partial blocks.

---

## Risk Assessment Matrix

| Fix                       | Risk    | Blast Radius | Reversibility | Dependencies |
|---------------------------|---------|--------------|---------------|--------------|
| 1.1 Walrus fix            | None    | Single line  | Trivial       | None         |
| 1.2 Coroutine leak        | Low     | WebSocket    | Easy          | None         |
| 1.3 Exception propagation | Low     | Lifecycle    | Easy          | 1.2          |
| 1.4 Drain thread          | Low     | Lifecycle    | Easy          | None         |
| 1.5 SharedMemory          | Medium  | Training     | Moderate      | None         |
| 1.6 Dead code             | None    | Single line  | Trivial       | None         |
| 1.7 Class extraction      | Medium  | Two files    | Moderate      | Tests        |
| 2.1 Key mismatch          | None    | Client       | Trivial       | None         |
| 2.2 Connection gate       | Low     | Adapter      | Easy          | 2.1          |
| 3.x Canopy UI             | Low-Med | Frontend     | Easy          | None         |
| 4.x Dark mode             | None    | CSS/Layout   | Trivial       | None         |
| 5.x Code quality          | None    | Cleanup      | Trivial       | None         |

---

## Verification Plan

### Per-Fix Verification

Each fix must pass:

1. Existing test suite (no regressions)
2. New unit test for the specific fix
3. Integration test where applicable

### End-to-End Verification

After all fixes:

1. Start juniper-cascor → training completes without failure
2. Start juniper-canopy → connects to cascor successfully
3. Monitor training → all metrics update in real-time
4. Verify all tabs render correctly in both light and dark mode
5. Verify network topology shows correct output node count
6. Verify decision boundary and dataset view aspect ratios
7. Run full test suites for both applications
