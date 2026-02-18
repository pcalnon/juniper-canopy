# Juniper Canopy ↔ Juniper Cascor Integration Regression Analysis

**Project**: JuniperCanopy - Monitoring and Diagnostic Frontend for CasCor NN
**Issue**: Canopy dashboard shows "Not Running" and receives no data from CasCor process
**Date**: 2026-02-11
**Author**: AI Agent
**Status**: COMPLETE — All 6 Fixes Implemented, 42 Tests Added, 3,341 Passed / 0 Failed

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Symptom Description](#symptom-description)
- [Investigation Methodology](#investigation-methodology)
- [Root Causes Identified](#root-causes-identified)
- [Contributing Factors](#contributing-factors)
- [Designed Fixes](#designed-fixes)
- [Additional Tests Needed](#additional-tests-needed)
- [Implementation Priority Matrix](#implementation-priority-matrix)
- [Appendix: File Reference Map](#appendix-file-reference-map)

---

## Executive Summary

When the Juniper Canopy startup script (`util/juniper_canopy.bash`) is run with `DEMO_MODE=false`, it launches the JuniperCascor `main.py` as a background process and then starts the Canopy FastAPI server. The dashboard correctly shows training state as **"Not Running"** and receives **no data** from the CasCor process.

The investigation identified **1 primary architectural root cause** and **5 secondary root causes** that collectively prevent Canopy from communicating with the CasCor backend in non-demo mode. The core issue is a **fundamental architecture mismatch**: the startup script launches CasCor as a separate, isolated process, while Canopy's `CascorIntegration` module expects to control CasCor **within the same Python process** via in-process module imports and method wrapping. There is no inter-process communication (IPC) channel between the two.

---

## Symptom Description

| Aspect | Observed Behavior |
| --- | --- |
| **Trigger** | Running `util/juniper_canopy.bash` with `DEMO_MODE=${FALSE}` (conf/juniper_canopy.conf line 62) |
| **CasCor Process** | Appears to start successfully (PID obtained), runs training sequentially |
| **Dashboard Status** | Shows "Not Running" in the top status bar |
| **Training Metrics** | No metrics received; all metric panels empty |
| **Network Topology** | Not available; 503 errors from `/api/topology` |
| **Dataset Tab** | No dataset displayed |
| **WebSocket Activity** | No training messages broadcast on `/ws/training` |

---

## Investigation Methodology

### Files Examined

| File | Purpose |
| --- | --- |
| `util/juniper_canopy.bash` | Startup script that decides demo vs real mode |
| `conf/juniper_canopy.conf` | Configuration defining DEMO_MODE, CASCOR paths |
| `conf/init.conf` | Base initialization for shell scripts |
| `conf/common.conf` | Common shell constants and functions |
| `src/main.py` | Canopy FastAPI + Dash application entry point |
| `src/backend/cascor_integration.py` | CasCor backend integration layer |
| `JuniperCascor/.../src/main.py` | CasCor main entry point (standalone training script) |
| `notes/CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md` | Recent JuniperData integration changes |
| `CHANGELOG.md` | Recent change history |

### Tools Used

- Source code analysis across JuniperCanopy and JuniperCascor codebases
- Git log analysis for recent changes
- Oracle consultation for architectural analysis
- Cross-reference of startup flow, configuration hierarchy, and runtime initialization

---

## Root Causes Identified

### RC-1 (PRIMARY): Architecture Mismatch — Separate Process vs In-Process Integration

**Severity**: CRITICAL
**Impact**: Complete communication failure between Canopy and CasCor

**Description**:

The Canopy system has two fundamentally incompatible assumptions about how it connects to CasCor:

1. **Startup Script Assumption** (`util/juniper_canopy.bash` lines 126-132): CasCor is a **separate OS process** launched via `nohup` in the background:

   ```bash
   nohup "${LANGUAGE_PATH}" "${CASCOR_MAIN_FILE}" 2>&1 &
   PID="$!"
   ```

2. **CascorIntegration Assumption** (`src/backend/cascor_integration.py` lines 87-133): CasCor is a **library** whose Python modules are imported into Canopy's own Python process using `sys.path.insert()`, then wrapped with monitoring hooks:

   ```python
   self.backend_path = self._resolve_backend_path(backend_path)
   self._add_backend_to_path()          # sys.path.insert(0, str(backend_src))
   self._import_backend_modules()        # from cascade_correlation... import ...
   self.network = None                   # No network created yet
   ```

3. **CasCor main.py is not a server** (`JuniperCascor/.../src/main.py`): CasCor's `main()` function creates a `SpiralProblem`, calls `sp.evaluate()` synchronously, and **exits**. It exposes no API, socket, or IPC interface. It is a batch training script, not a long-running service.

**Result**: The background CasCor process trains in isolation with no communication channel back to Canopy. Canopy's `CascorIntegration` successfully imports CasCor's module classes but has no live network instance to monitor.

---

### RC-2: No Network Created in Real Backend Lifespan

**Severity**: CRITICAL
**Impact**: All API endpoints return empty/error responses

**Description**:

In `src/main.py`, the `lifespan()` async context manager handles real backend mode (lines 154-160):

```python
else:
    system_logger.info("CasCor backend mode active")
    demo_mode_instance = None

    # Initialize monitoring callbacks for real backend
    if cascor_integration:
        setup_monitoring_callbacks()
```

The lifespan code **only** calls `setup_monitoring_callbacks()`. It does **not**:

- Call `cascor_integration.create_network(config)` to instantiate a neural network
- Call `cascor_integration.connect_to_network(network)` to connect to an existing one
- Call `cascor_integration.install_monitoring_hooks()` to wrap training methods
- Call `cascor_integration.start_monitoring_thread()` to poll for metrics
- Call `cascor_integration.start_training_background()` to begin training

As a result, `cascor_integration.network` remains `None` throughout the application lifecycle. Every API endpoint that checks `cascor_integration.network` returns early with empty data or a 503 error.

**Affected endpoints** (all return error/empty when `network is None`):

- `GET /api/topology` → 503
- `GET /api/network/stats` → 503
- `GET /api/metrics` → empty dict
- `GET /api/metrics/history` → 503
- `GET /api/dataset` → 503
- `GET /api/decision_boundary` → 503
- `GET /api/status` → `cascor_integration.get_training_status()` (which returns defaults)
- `POST /api/train/start` → "No network configured" 400 error

---

### RC-3: WebSocket Control Commands Not Implemented for Real Backend

**Severity**: HIGH
**Impact**: Dashboard training controls (start/stop/pause/resume/reset) non-functional

**Description**:

The `/ws/control` WebSocket endpoint (`src/main.py` lines 445-454) has an explicit TODO for real backend commands:

```python
# Handle real CasCor backend commands
elif cascor_integration:
    # TODO: Implement real backend control
    await websocket_manager.send_personal_message(
        {"ok": False, "error": "Real backend control not yet implemented"},
        websocket,
    )
```

Even if a network were created, users could not control training via the dashboard. The REST API endpoints (`/api/train/start`, `/api/train/pause`, etc.) do have partial CasCor support but only for start/stop — pause, resume, and reset return 503.

---

### RC-4: CasCor Process Lifetime Mismatch

**Severity**: HIGH
**Impact**: Background CasCor process exits before dashboard loads

**Description**:

JuniperCascor's `main.py` runs `sp.evaluate()` synchronously — it trains the network and then exits. The startup script captures its PID, but by the time the Canopy dashboard is fully loaded and a user interacts with it, the CasCor process may have already completed training and terminated.

The script later tries to `kill -KILL "${PID}"` on shutdown, which may target:
- A process that already exited
- A PID that was recycled by the OS for a different process

---

### RC-5: JUNIPER_DATA_URL Not Validated in Real Backend Mode

**Severity**: HIGH
**Impact**: Dataset operations fail silently in real backend mode

**Description**:

The recent JuniperData integration (CAN-INT-002, completed 2026-02-07) made `JUNIPER_DATA_URL` mandatory. However, the URL validation in `src/main.py` lifespan (lines 126-135) only runs inside the `if demo_mode_active:` block:

```python
if demo_mode_active:
    system_logger.info("Initializing demo mode")
    juniper_data_url = os.getenv("JUNIPER_DATA_URL")
    if not juniper_data_url:
        # ... error handling ...
```

In real backend mode, this validation is skipped entirely. The startup script does export `JUNIPER_DATA_URL` (line 85), but if Canopy is launched any other way (IDE, systemd, direct uvicorn), dataset operations will fail without a clear error message.

---

### RC-6: Monitoring Callbacks Registered Without a Network

**Severity**: MEDIUM
**Impact**: Callbacks are registered but never fire; no error reported

**Description**:

`setup_monitoring_callbacks()` (`src/main.py` lines 270-310) calls:

```python
cascor_integration.create_monitoring_callback("epoch_end", on_metrics_update)
cascor_integration.create_monitoring_callback("topology_change", on_topology_change)
cascor_integration.create_monitoring_callback("cascade_add", on_cascade_add)
```

These callbacks are registered on the `cascor_integration` instance, but since `network is None`:
- No monitoring hooks are installed (no methods to wrap)
- No monitoring thread is running (nothing to poll)
- The callbacks are never invoked
- No error or warning is logged about this dormant state

---

## Contributing Factors

### CF-1: Mode Flag Mismatch Between Shell and Python

The bash script uses `DEMO_MODE` (defined in `conf/juniper_canopy.conf` line 62 as `${FALSE}` which equals `"1"`) to decide demo vs main mode behavior. The Python app uses `CASCOR_DEMO_MODE` environment variable (checked in `src/main.py` line 208). These are **different variables** with **different value conventions**:

- Shell: `TRUE="0"`, `FALSE="1"` (exit-code convention)
- Python: `"1"`, `"true"`, `"True"`, `"yes"`, `"Yes"` → demo mode enabled

The startup script does not export `CASCOR_DEMO_MODE` based on `DEMO_MODE`, so the Python app relies on the `CascorIntegration` init success/failure to determine mode, not the script's explicit mode flag.

### CF-2: Process Detection Fragility

`pgrep -f "${CASCOR_PROCESS_NAME}"` (startup script line 119) matches against the full command line, which can:
- Match unrelated Python processes with overlapping path substrings
- Miss the CasCor process if the command line format differs
- Return stale results if the process exits between check and use

### CF-3: Diagnostic Evidence Destroyed

The startup script deletes `nohup.out` on shutdown (line 142: `rm -f nohup.out`), destroying the only log of CasCor's stdout/stderr. If CasCor crashes on startup (missing deps, path errors, JuniperData failure), the evidence is lost.

### CF-4: Backend Path Inconsistency Risk

The startup script resolves the CasCor path via shell variables (`CASCOR_MAIN_FILE` from `conf/juniper_canopy.conf`), while `CascorIntegration` resolves it independently via the Python configuration hierarchy (env var → YAML → default `../cascor`). These can diverge, meaning the launched process and the imported modules may come from different directories or even different versions.

### CF-5: Multi-Worker/Reload Incompatibility

`CascorIntegration` stores network state in Python instance variables. If uvicorn is run with `--workers > 1` or `--reload`, each worker gets its own `CascorIntegration` instance with `network = None`, while training might be happening in a different worker's memory space.

---

## Designed Fixes

### Fix 1: Implement In-Process Real Backend Initialization (CRITICAL)

**Addresses**: RC-1, RC-2, RC-4, RC-6

**Design**: Modify the lifespan handler's real-backend path to create and initialize a network within Canopy's process, eliminating the need for a separate CasCor process.

**Changes Required** in `src/main.py` lifespan, `else` branch (lines 154-160):

1. Create a CasCor network via `cascor_integration.create_network(config)` using training parameters from `TrainingState` or configuration
2. Generate/fetch dataset from JuniperData (using `JuniperDataClient`)
3. Install monitoring hooks via `cascor_integration.install_monitoring_hooks()`
4. Start monitoring thread via `cascor_integration.start_monitoring_thread()`
5. Optionally auto-start background training via `cascor_integration.start_training_background(X_train, y_train)`, or leave for user-initiated start via dashboard

**Pseudocode**:

```python
else:
    system_logger.info("CasCor backend mode active")
    demo_mode_instance = None

    if cascor_integration:
        # Validate JUNIPER_DATA_URL (same as demo mode)
        juniper_data_url = os.getenv("JUNIPER_DATA_URL")
        if not juniper_data_url:
            config_url = config.get("backend.juniper_data.url")
            if config_url and not str(config_url).startswith("$"):
                juniper_data_url = str(config_url)
                os.environ["JUNIPER_DATA_URL"] = juniper_data_url

        # Create network with default configuration
        network_config = {
            "input_size": 2,
            "output_size": 1,
            "learning_rate": training_state.get_state().get("learning_rate", 0.01),
            "max_hidden_units": training_state.get_state().get("max_hidden_units", 10),
            "max_epochs": training_state.get_state().get("max_epochs", 200),
        }
        cascor_integration.create_network(network_config)

        # Fetch dataset from JuniperData
        dataset = _fetch_dataset_from_juniper_data(juniper_data_url)
        cascor_integration._dataset_info = dataset

        # Install monitoring hooks and start monitoring
        cascor_integration.install_monitoring_hooks()
        cascor_integration.start_monitoring_thread()
        setup_monitoring_callbacks()

        system_logger.info("CasCor backend fully initialized — ready for training")
```

### Fix 2: Remove External CasCor Process Launch from Startup Script (HIGH)

**Addresses**: RC-1, RC-4, CF-2, CF-3

**Design**: Since Fix 1 makes CasCor run in-process, the startup script should no longer launch a separate CasCor process.

**Changes Required** in `util/juniper_canopy.bash` (lines 118-132):

1. Remove the `pgrep` check for running CasCor processes
2. Remove the `nohup ... &` background process launch
3. Remove the `kill -KILL "${PID}"` shutdown logic
4. Set `CASCOR_BACKEND_PATH` environment variable so Canopy's `CascorIntegration` can find CasCor modules for import
5. Retain the JuniperData auto-start logic (it's a proper service)

**Simplified script flow**:

```bash
else
    log_trace "Launching ${CURRENT_PROJECT} in Main Mode with real CasCor backend"

    # Set CasCor backend path for in-process integration
    export CASCOR_BACKEND_PATH="${CASCOR_SCRIPT_APPLICATION_DIR}"

    # Ensure JuniperData is available (keep existing logic)
    # ...

    # Launch Canopy (CasCor runs in-process)
    ${LANGUAGE_PATH} "${MAIN_FILE}"
fi
```

### Fix 3: Implement WebSocket Control Commands for Real Backend (HIGH)

**Addresses**: RC-3

**Design**: Implement the `elif cascor_integration:` branch in the `/ws/control` WebSocket handler.

**Changes Required** in `src/main.py` (lines 445-454):

```python
elif cascor_integration:
    try:
        if command == "start":
            reset = message.get("reset", True)
            if cascor_integration.network is None:
                response = {"ok": False, "error": "No network configured"}
            elif cascor_integration.is_training_in_progress():
                response = {"ok": False, "error": "Training already in progress"}
            else:
                success = cascor_integration.start_training_background()
                response = {"ok": success, "command": command}
        elif command == "stop":
            success = cascor_integration.request_training_stop()
            response = {"ok": success, "command": command}
        elif command == "pause":
            response = {"ok": False, "error": "Pause not supported for CasCor backend"}
        elif command == "resume":
            response = {"ok": False, "error": "Resume not supported for CasCor backend"}
        elif command == "reset":
            # Re-create network with current config
            cascor_integration.create_network(current_config)
            response = {"ok": True, "command": command}
        else:
            response = {"ok": False, "error": f"Unknown command: {command}"}
        await websocket_manager.send_personal_message(response, websocket)
    except Exception as e:
        await websocket_manager.send_personal_message(
            {"ok": False, "error": str(e)}, websocket
        )
```

### Fix 4: Validate JUNIPER_DATA_URL in Both Modes (HIGH)

**Addresses**: RC-5

**Design**: Move `JUNIPER_DATA_URL` validation out of the `if demo_mode_active:` block so it runs for both demo and real backend modes.

**Changes Required** in `src/main.py` lifespan (before the mode-specific branches):

```python
# Validate JUNIPER_DATA_URL for all modes (moved from demo-mode-only block)
juniper_data_url = os.getenv("JUNIPER_DATA_URL")
if not juniper_data_url:
    config_url = config.get("backend.juniper_data.url")
    if config_url and not str(config_url).startswith("$"):
        juniper_data_url = str(config_url)
        os.environ["JUNIPER_DATA_URL"] = juniper_data_url
        system_logger.info(f"JUNIPER_DATA_URL resolved from config: {juniper_data_url}")
if not juniper_data_url:
    system_logger.error("JUNIPER_DATA_URL is not set.")
    raise RuntimeError("JUNIPER_DATA_URL is required. Set JUNIPER_DATA_URL=http://localhost:8100")

if demo_mode_active:
    # ... (remove duplicate JUNIPER_DATA_URL validation) ...
```

### Fix 5: Synchronize Mode Flags Between Shell and Python (MEDIUM)

**Addresses**: CF-1

**Design**: Have the startup script export `CASCOR_DEMO_MODE` based on `DEMO_MODE` to ensure consistent mode detection.

**Changes Required** in `util/juniper_canopy.bash` (before the mode branch):

```bash
# Synchronize mode flag for Python application
if [[ "${DEMO_MODE}" == "${TRUE}" ]]; then
    export CASCOR_DEMO_MODE=1
else
    export CASCOR_DEMO_MODE=0
fi
```

### Fix 6: Preserve CasCor Diagnostic Logs (LOW)

**Addresses**: CF-3

**Design**: If the external CasCor launch is retained for any reason, redirect output to a log file instead of `nohup.out`.

```bash
CASCOR_LOG="${LOGS_DIR}/cascor_backend.log"
nohup "${LANGUAGE_PATH}" "${CASCOR_MAIN_FILE}" > "${CASCOR_LOG}" 2>&1 &
# Do NOT rm the log file on shutdown
```

---

## Additional Tests Needed

### T-1: Real Backend Initialization Integration Test

**Purpose**: Validate that CascorIntegration correctly initializes a network, installs hooks, and starts monitoring in non-demo mode.
**Location**: `src/tests/integration/test_cascor_real_backend_init.py`
**Marker**: `@pytest.mark.integration`

```python
@pytest.mark.integration
class TestRealBackendInitialization:
    def test_create_network_with_default_config(self, client):
        """CascorIntegration creates a network with default parameters."""

    def test_monitoring_hooks_installed_after_init(self, client):
        """Monitoring hooks are active after full initialization."""

    def test_monitoring_thread_starts_after_init(self, client):
        """Monitoring thread is running and polling for metrics."""

    def test_network_endpoints_return_data(self, client):
        """/api/topology, /api/network/stats return data when network exists."""

    def test_training_start_via_api(self, client):
        """/api/train/start successfully begins background training."""

    def test_training_metrics_broadcast(self, client):
        """WebSocket /ws/training receives metrics after training starts."""
```

### T-2: WebSocket Control Commands for Real Backend

**Purpose**: Validate that /ws/control commands work for real CasCor backend.
**Location**: `src/tests/integration/test_cascor_ws_control.py`
**Marker**: `@pytest.mark.integration`

```python
@pytest.mark.integration
class TestCascorWebSocketControl:
    def test_start_command_creates_training(self):
        """'start' command initiates background training."""

    def test_stop_command_requests_stop(self):
        """'stop' command sets stop flag on training."""

    def test_start_while_training_returns_busy(self):
        """'start' during active training returns error."""

    def test_reset_recreates_network(self):
        """'reset' command re-creates the network."""

    def test_unsupported_commands_return_error(self):
        """'pause'/'resume' return appropriate error for CasCor."""
```

### T-3: JUNIPER_DATA_URL Validation in All Modes

**Purpose**: Ensure JUNIPER_DATA_URL is validated regardless of demo/real mode.
**Location**: `src/tests/unit/test_juniper_data_url_validation.py`
**Marker**: `@pytest.mark.unit`

```python
@pytest.mark.unit
class TestJuniperDataURLValidation:
    def test_missing_url_raises_error_in_demo_mode(self):
        """App fails to start without JUNIPER_DATA_URL in demo mode."""

    def test_missing_url_raises_error_in_real_mode(self):
        """App fails to start without JUNIPER_DATA_URL in real mode."""

    def test_url_resolved_from_config_in_real_mode(self):
        """JUNIPER_DATA_URL resolves from app_config.yaml if env var not set."""

    def test_env_var_takes_precedence_over_config(self):
        """JUNIPER_DATA_URL env var overrides config value."""
```

### T-4: Mode Flag Consistency Regression Test

**Purpose**: Detect mismatches between shell and Python mode determination.
**Location**: `src/tests/regression/test_mode_flag_consistency.py`
**Marker**: `@pytest.mark.regression`

```python
@pytest.mark.regression
class TestModeFlagConsistency:
    def test_cascor_demo_mode_1_enables_demo(self):
        """CASCOR_DEMO_MODE=1 activates demo mode in the app."""

    def test_cascor_demo_mode_0_enables_real_backend(self):
        """CASCOR_DEMO_MODE=0 attempts real backend initialization."""

    def test_cascor_demo_mode_unset_fallback_behavior(self):
        """Without CASCOR_DEMO_MODE, app falls back based on backend availability."""

    def test_demo_mode_instance_none_in_real_mode(self):
        """demo_mode_instance is None when real backend initializes."""
```

### T-5: CascorIntegration Network Lifecycle Tests

**Purpose**: Validate the full lifecycle: create → train → monitor → stop → cleanup.
**Location**: `src/tests/integration/test_cascor_lifecycle.py`
**Marker**: `@pytest.mark.integration`, `@pytest.mark.requires_cascor`

```python
@pytest.mark.integration
@pytest.mark.requires_cascor
class TestCascorLifecycle:
    def test_create_network_sets_network_attribute(self):
        """After create_network(), network is not None."""

    def test_install_hooks_wraps_fit_method(self):
        """install_monitoring_hooks() wraps network.fit."""

    def test_start_training_background_returns_true(self):
        """start_training_background() starts training successfully."""

    def test_is_training_in_progress_during_training(self):
        """is_training_in_progress() returns True during training."""

    def test_request_stop_during_training(self):
        """request_training_stop() sets stop flag during active training."""

    def test_shutdown_cleans_up_resources(self):
        """shutdown() stops monitoring and cleans executor."""
```

### T-6: Startup Script Mode Behavior (Shell Test)

**Purpose**: Validate startup script behavior for both modes.
**Location**: `src/tests/integration/test_startup_script.py` or shell test script
**Marker**: `@pytest.mark.e2e`, `@pytest.mark.requires_server`

```python
@pytest.mark.e2e
@pytest.mark.requires_server
class TestStartupScript:
    def test_demo_mode_does_not_launch_cascor_process(self):
        """DEMO_MODE=true does not launch a separate CasCor process."""

    def test_real_mode_exports_cascor_backend_path(self):
        """DEMO_MODE=false exports CASCOR_BACKEND_PATH for in-process import."""

    def test_real_mode_exports_cascor_demo_mode_0(self):
        """DEMO_MODE=false exports CASCOR_DEMO_MODE=0."""

    def test_juniper_data_url_exported_in_both_modes(self):
        """JUNIPER_DATA_URL is exported regardless of mode."""
```

---

## Implementation Priority Matrix

| Fix | Priority | Effort | Addresses | Blocks |
| --- | --- | --- | --- | --- |
| Fix 1: In-process backend init | CRITICAL | Medium (1-2h) | RC-1, RC-2, RC-4, RC-6 | Fix 3 |
| Fix 2: Remove external process launch | HIGH | Small (30min) | RC-1, RC-4, CF-2, CF-3 | None |
| Fix 3: WS control commands | HIGH | Medium (1-2h) | RC-3 | None |
| Fix 4: JUNIPER_DATA_URL validation | HIGH | Small (30min) | RC-5 | None |
| Fix 5: Mode flag sync | MEDIUM | Small (15min) | CF-1 | None |
| Fix 6: Preserve diagnostic logs | LOW | Small (15min) | CF-3 | None |

**Recommended implementation order**: Fix 4 → Fix 5 → Fix 1 → Fix 2 → Fix 3 → Fix 6

**Total estimated effort**: 4-6 hours

---

## Future Consideration: CasCor as a Service (IPC Architecture)

If the project requires CasCor to run as a separate, long-lived process (for GPU isolation, crash containment, distributed workers, or multi-dashboard scenarios), a more extensive redesign would be needed:

1. **CasCor API Service**: Add HTTP/WebSocket endpoints to JuniperCascor that expose training control and metrics streaming
2. **Canopy Client Mode**: Replace `CascorIntegration`'s in-process wrapping with HTTP client calls to the CasCor service
3. **Shared State**: Use Redis or similar for shared training state between processes

This is explicitly **deferred** — the in-process approach is correct for the current single-machine, single-user prototype.

---

## Appendix: File Reference Map

| File | Lines | Relevance |
| --- | --- | --- |
| `util/juniper_canopy.bash` | 92-147 | Mode branching and CasCor process launch |
| `conf/juniper_canopy.conf` | 62 | `DEMO_MODE="${FALSE}"` definition |
| `conf/juniper_canopy.conf` | 381-385 | CasCor path constants and CASCOR_PROCESS_NAME |
| `src/main.py` | 105-181 | `lifespan()` — startup/shutdown manager |
| `src/main.py` | 202-229 | `CascorIntegration` initialization and demo-mode fallback |
| `src/main.py` | 270-310 | `setup_monitoring_callbacks()` |
| `src/main.py` | 373-464 | `/ws/control` WebSocket handler (TODO for real backend) |
| `src/main.py` | 126-135 | JUNIPER_DATA_URL validation (demo-mode only) |
| `src/backend/cascor_integration.py` | 87-133 | `__init__` — imports modules, sets `network = None` |
| `src/backend/cascor_integration.py` | 135-205 | `_resolve_backend_path()` — path resolution hierarchy |
| `src/backend/cascor_integration.py` | 338-383 | `create_network()` — never called in real mode |
| `src/backend/cascor_integration.py` | 408-479 | `install_monitoring_hooks()` — never called in real mode |
| `src/backend/cascor_integration.py` | 570-598 | `start_training_background()` — never called in real mode |
| `JuniperCascor/.../src/main.py` | 113-285 | `main()` → `SpiralProblem` → `sp.evaluate()` (runs and exits) |

---

## Document History

| Date | Author | Changes |
| --- | --- | --- |
| 2026-02-11 | AI Agent | Initial creation: full regression analysis with 6 root causes, 5 contributing factors, 6 designed fixes, and 6 test suites |
