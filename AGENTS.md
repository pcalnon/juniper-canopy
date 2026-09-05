# Juniper Canopy - Agent Development Guide

**Project**: juniper-canopy — Real-Time Monitoring Dashboard for Juniper
**Repository**: pcalnon/juniper-canopy
**Author**: Paul Calnon
**License**: MIT License
**Version**: 0.6.0
**Last Updated**: 2026-09-05

---

## Hazards (resident — do not relocate)

Directives whose **non-application destroys work**. Everything else in this file may be demoted to
the `docs/` tree under the memory budget; these may not, because a pointer only helps an agent that
already knows to look. Adding a new hazard here is legitimate — ratchet space out of a reference
section in the same PR rather than waiving the budget gate.

- **Dash `no_update` chaining, and the duplicate writer it creates.** A clientside producer that
  idles with `no_update` must never be an `Input` to an interval-driven callback **that shares its
  tick**: the dependent callback is skipped for that tick, so the lane fires only when the producer
  does — silently, with no error and no failing test. Route such a signal by what the callback needs
  from it. **Read-only → `State`** (`ws-liveness-store`), and there is no second writer. **Must
  drive an update → `State` cannot serve it** (State does not trigger), so it goes to a separate
  `allow_duplicate` callback (`ws-metrics-buffer`) — and that callback co-owns the store id, so the
  must-drive branch **always** produces a second writer. Therefore: **before reasoning from a
  store's write census, count its writers — grep the store id, not the callback.** An
  `allow_duplicate` `Output` is invisible to anyone reading the handler they happened to open.
  `metrics-panel-metrics-store` has two writers and only one carries an identity guard
  (`dashboard_manager.py` `:3877` guarded poll, `:3909` unguarded append).
- **Do not change existing payload keys without versioning.** Add new keys as optional and update
  dashboard consumers before changing a contract. The failure is silent to the author and breaks
  clients.
- **No global mutable state without locks.** All shared state uses `threading.Lock()`;
  `TrainingState`'s lock is load-bearing. A lockless shared write corrupts a run with no error.
- **Long-lived collections must be size-bounded.** Use `maxlen` for deques and cap history buffers
  (`REPLAY_WEIGHT_BUFFER_MAX` reasons about a few-hundred-MB peak). Unbounded growth kills a long
  run with no warning.
- **`/tmp/` is prohibited** as the home for any script that produces, modifies or analyzes
  repository content — it is reaped and the scripts are irrecoverable. Scratch *data* there is fine;
  source files are not. Full rule and the motivating incident: § File Placement Rules.
- **Plotly trace *names* are a cross-language contract with the clientside JS — renaming one
  silently mis-appends live data to the wrong trace.** Trace 0 of each plot is the WS-bridge
  `extendTraces` target (appended by index); every other series is looked up by its exact **display
  name** via `findTraceIndex` (`components/metrics_panel.py:850`) against the constants at
  `metrics_panel.py:78-79` (`OUTPUT_TRACE_NAME`, `ACCURACY_TRACE_NAME`). A mismatch does not raise —
  the lookup simply misses and WS points land on the wrong series, so the chart keeps updating and
  is wrong. Both sides are pinned together by
  `src/tests/unit/frontend/test_n9_metrics_visualization.py`; change a name in one place only by
  changing it in all three.
- **The pinned-params store must be MERGED, never replaced wholesale.**
  `update_pinned_params_store` (`dashboard_manager.py:4183`) takes the existing store as a `State`
  and delegates to `_merge_pinned_params` (`:6121`) for a reason: its pattern-match `Input` sees
  only the pin checkboxes **currently in the DOM**, and the Parameters tables are rebuilt on every
  params-store change, so any render while the store is empty or stale (mount before
  `storage_type="local"` hydration, or a tab whose tables are not rendered) under-reports the real
  pin set. A wholesale replace then asserts "not pinned" for every key it could not see, and the
  next toggle persists that under-report — **silently discarding pins made before a reload**
  (F-CANOPY-018 / F-CANOPY-028). Write only what you can actually observe; preserve the rest.
- **Route the cascor status *class*, not the raw payload (X7 slice 1c).** In service mode
  `/api/status` serves a cache envelope (`status_class`, `stale`, `age_seconds`). A half-dead
  200 has no `error`, so the legacy status-bar branch renders **"Stopped"** — the PR #340 lie.
  The cache publishes what it concluded; the UI renders that. Do not feed `get_training_status`
  to the refresher (it shares `_cb` with five other sites and freezes the cache INDETERMINATE
  for 60 s against a healthy upstream) — use `get_training_status_for_refresh`. Do not invent
  `is_training: False` when no OK has been seen. Do not widen `is_training_active()` to a
  tri-state. Age out on the last **attempt**, not the last success. Lands with `#578`. Runbook:
  [`docs/AGENTS_REFERENCE.md` § Cascor status cache](docs/AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c).

## Project Overview

The juniper_canopy prototype is a real-time monitoring and diagnostic frontend for the Cascade Correlation Neural Network (CasCor) prototype. It provides:

- Real-time network training visualization
- Interactive decision boundary plotting
- Network topology visualization with dynamic updates
- Training metrics and performance statistics
- Demo mode for development without backend connection
- Standardized WebSocket message protocol

## AI Agent Quick Start

### Conda Environment

> **Required:** Activate the live `JuniperCanopy1` conda environment before running any commands. The env name is **versioned** — rebuilds increment the suffix and rename the old env `*-DEPRECATED` (never activate those). Discover yours with `conda env list | grep JuniperCanopy`.

```bash
conda activate JuniperCanopy1   # live env; see the note above
```

For agents and subagents working on this codebase, follow this checklist:

1. **Run the app in demo mode**

   ```bash
   ./demo
   # or: ./util/juniper_canopy-demo.bash
   ```

2. **Run fast tests only (no external deps)**

   ```bash
   cd src
   pytest -m "unit and not slow" -v
   ```

3. **Before changing configuration**
   - Check `src/settings.py` (Pydantic BaseSettings), `src/canopy_constants.py`, and `conf/app_config.yaml`
   - Respect the hierarchy: Pydantic Settings (`JUNIPER_CANOPY_*` env vars) > YAML > constants
   - Legacy `CASCOR_*` env vars are supported with deprecation warnings

4. **Before changing WebSocket or API routes**
   - Update both FastAPI (`main.py`, `communication/websocket_manager.py`) and any Dash callbacks using those routes
   - Update `docs/api/` and tests in `src/tests/integration/`

5. **Before changing demo mode behavior**
   - Understand `src/demo_mode.py` and how `JUNIPER_CANOPY_DEMO_MODE` (or legacy `CASCOR_DEMO_MODE`) controls app startup
   - Ensure `./demo` still starts successfully and tests still pass

6. **Singleton reset guidance**
   - If you add new singleton-like components, extend the `reset_singletons` fixture in `src/tests/conftest.py`

**Where to find more details:**

- [Constants Guide](docs/cascor/CONSTANTS_GUIDE.md)
- [Testing Docs](docs/testing/)
- [CasCor Backend Integration](docs/cascor/)
- [API Documentation](docs/api/)

## Quick Start Commands

### Running the Application

```bash
# Run in demo mode (development/testing)
./demo

# Or use the full script path
./util/juniper_canopy-demo.bash

# Run with real CasCor backend (production-like)
# Ensure CASCOR_DEMO_MODE is NOT set, and backend is available at CASCOR_BACKEND_PATH
cd src
uvicorn main:app --host 0.0.0.0 --port 8050 --log-level info
```

> **Note:** The canonical way to run the application is via `uvicorn main:app`. The `./demo` script handles conda activation and environment setup automatically.

### Testing

```bash
# Run all tests
cd src
pytest tests/ -v

# Run all tests with coverage
cd src
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Run specific test file
cd src
pytest tests/unit/test_config_manager.py -v

# Run with coverage (detailed)
cd src
pytest tests/ --cov=. --cov-report=html:../reports/coverage --cov-report=term-missing

# Run integration tests only
cd src
pytest tests/integration/ -v

# Run unit tests only
cd src
pytest tests/unit/ -v

# Run by marker
cd src
pytest -m unit -v
pytest -m integration -v
pytest -m "not requires_cascor" -v

# View coverage report
open reports/coverage/index.html  # macOS
xdg-open reports/coverage/index.html  # Linux
```

### Coverage

Reproduce the CI coverage gate locally (full suite):

```bash
make coverage                 # convenience wrapper
bash util/run_coverage.bash   # source of truth (mirrors .github/workflows/ci.yml)
```

Gate: 80% aggregate (override with `COVERAGE_FAIL_UNDER=<n>`). The script runs the full gated suite by design so the percentage matches CI; for a narrower run use plain `pytest`.

#### Pytest Markers

| Marker             | Meaning                                   | Typical use                                 |
| ------------------ | ----------------------------------------- | ------------------------------------------- |
| `unit`             | Fast tests, no external dependencies      | Pure logic / small components               |
| `integration`      | Integration tests (DB, FS, backend, etc.) | Backend + frontend wiring, config, I/O      |
| `regression`       | Regression tests for fixed bugs           | Guarding against previously-fixed issues    |
| `performance`      | Performance / benchmark tests             | Throughput, latency, allocation checks      |
| `e2e`              | Full end-to-end tests                     | Full stack with real services               |
| `slow`             | Tests > 1s                                | Load-heavy, large data, long-running loops  |
| `requires_cascor`  | Needs a real CasCor backend               | Real backend integration tests              |
| `requires_server`  | Needs a running server                    | External client tests vs pre-started server |
| `requires_redis`   | Needs Redis                               | Cache / pub-sub integration tests           |
| `requires_cassandra` | Needs Cassandra connection              | Cassandra integration tests                 |
| `requires_display` | Needs a GUI/display                       | Visualization / UI snapshot tests           |
| `api`              | API endpoint tests                        | FastAPI route / response tests              |
| `generators`       | Data generator tests                      | Test data generation functions              |

Example marker usage:

```bash
# Run only regression tests
cd src
pytest tests/regression/ -v

# Run all tests except slow and CasCor-dependent
pytest -m "not slow and not requires_cascor" -v

# Run only performance benchmarks
pytest -m performance -v
```

#### Test Environment Variables

The test suite auto-skips certain tests unless you opt in via environment variables:

| Variable                   | Effect                                                          | Default |
| -------------------------- | --------------------------------------------------------------- | ------- |
| `CASCOR_BACKEND_AVAILABLE` | Enable tests marked `requires_cascor`                           | unset   |
| `RUN_SERVER_TESTS`         | Enable tests marked `requires_server`                           | unset   |
| `RUN_DISPLAY_TESTS`        | Enable tests marked `requires_display` in headless environments | unset   |
| `ENABLE_SLOW_TESTS`        | Run tests marked `slow`                                         | unset   |
| `CASSANDRA_INTEGRATION_TEST` | Enable Cassandra integration tests                            | unset   |
| `REDIS_INTEGRATION_TEST`  | Enable Redis integration tests                                  | unset   |
| `JUNIPER_DATA_E2E_TEST`   | Enable JuniperData end-to-end tests                             | unset   |

> **Note:** `conftest.py` **forces** `JUNIPER_CANOPY_DEMO_MODE=1` for the test process by default so tests do **not** require a real backend unless you explicitly enable it via `CASCOR_BACKEND_AVAILABLE=1`.

Example:

```bash
# Enable CasCor backend and slow tests
export CASCOR_BACKEND_AVAILABLE=1
export ENABLE_SLOW_TESTS=1
cd src
pytest -m "not requires_display" -v
```

#### Key Test Fixtures

These fixtures are defined in `src/tests/conftest.py` and are available everywhere under `src/tests/`:

- **`client`** (module scope): FastAPI `TestClient` against `main.app` with `JUNIPER_CANOPY_DEMO_MODE=1`. Use this for exercising API endpoints in tests without starting uvicorn.

- **`mock_juniper_data_client`** (session scope, autouse): Mocks `JuniperDataClient` with realistic spiral dataset responses. Generates 200-sample 2-class spiral data. Required for all tests that touch data fetching.

- **`reset_singletons`** (function scope, autouse): Resets `ConfigManager`, `DemoMode`, `Settings`, `CallbackContextAdapter`, and security state singletons before and after each test. **Agent guidance:** Do not bypass this fixture; if you introduce new singletons, extend this fixture to reset them.

- **`preserve_metrics_layouts`** (session scope, autouse): Backs up and restores `conf/layouts/metrics_layouts.json` to prevent tests from polluting the working tree.

- **`cleanup_test_environment`** (function scope, autouse): Clears test-specific environment variables after each test.

- **`fake_backend_root`**: Creates a fake CasCor backend modules tree under a temporary directory. Use it to test backend behavior without a real backend.

- **`ensure_test_data_directory`** (session scope, autouse): Ensures `src/tests/data/` exists and creates `sample_metrics.json` if missing.

- **`test_config`** (function scope): Provides a safe-defaults configuration dictionary for tests.

- **`sample_training_metrics`, `sample_network_topology`, `sample_dataset`**: Provide realistic test data for metrics/topology/dataset-related code.

Example usage:

```python
@pytest.mark.unit
def test_get_topology_uses_demo_mode(client, sample_network_topology):
    """Example usage of client fixture."""
    response = client.get("/api/network/topology")
    assert response.status_code == 200
```

### Code Quality

```bash
# Install pre-commit hooks (one-time setup)
pip install pre-commit
pre-commit install

# Run pre-commit hooks manually
pre-commit run --all-files

# Run specific checks
black src/ --check --diff
isort src/ --check-only --diff
flake8 src/ --max-line-length=512 --statistics
mypy src/ --ignore-missing-imports

# Auto-format code
black src/
isort src/

# Check for syntax errors
python -m py_compile src/**/*.py
```

### Observability — Prometheus Collectors

For any new `prometheus_client` `Counter` / `Gauge` / `Histogram` / `Summary` / `Info` / `Enum` registration, use the canonical helpers from `juniper-observability` (`>=0.2.0`):

- `register_or_reuse(factory, name, *args, **kwargs)` — adopt-existing on duplicate (the default for almost every call site; preserves accumulated samples across in-process re-init).
- `register_fresh(...)` — drop-and-recreate on duplicate (only when args genuinely differ).
- `register_info_or_update(name, description, **labels)` — sugar for the `Info` two-step register-then-`.info({...})` pattern.
- `lazy_register_or_reuse(...)` — for the lazy-init-with-`None`-sentinel pattern.

Tests touching these collectors should use `juniper_observability.testing.reset_prometheus_registry`. Existing examples in this repo: `src/observability.py:_ensure_canopy_metrics`, `src/main.py` (browser WS metrics), `src/adapter_validation.py`, `src/frontend/dashboard_manager.py`. See [the design doc in juniper-ml](https://github.com/pcalnon/juniper-ml/blob/main/notes/observability/JUNIPER_2026-05-05_JUNIPER-ML_REGISTER-OR-REUSE-HELPER-DESIGN.md) for the rationale.

### CI/CD

**GitHub Actions Workflows** (`.github/workflows/`):

| Workflow | File | Purpose |
|----------|------|---------|
| Continuous Integration | `ci.yml` | Test, lint, type-check on PR and push |
| CodeQL Analysis | `codeql.yml` | Python SAST; required check `Analyze (python)`. SHA-pinned v4; Dependabot `codeql-action` group also bumps `ci.yml` Bandit `upload-sarif`. |
| Lockfile Update | `lockfile-update.yml` | Automated dependency lock updates |
| Publish | `publish.yml` | Release publishing automation |
| Security Scan | `security-scan.yml` | Security vulnerability scanning |
| Sequence Safety (Advisory) | `sequence-safety.yml` | Per-PR advisory compositional-loss screen (AST symbol-loss + docs deletion-magnitude, `src/**/*.py` symbol scope) via the packaged `juniper-ci-tools` console scripts; standalone, never a required check |
| Post-Merge Main Verification | `main-verify.yml` | Bypass-proof post-merge sequence-safety net (screens-only; per-SHA no-cancel; catch-up base; stable-title tracking-issue notify) |

```bash
# Local CI simulation (requires act - optional)
act -j test

# Check workflow syntax
cat .github/workflows/ci.yml | grep -E "^(name|on|jobs)"

# View CI results
# GitHub Actions → Your Workflow → View details

# Download artifacts
# GitHub Actions → Workflow Run → Artifacts section
```

### Development Tools

```bash
# Check for syntax errors
python -m py_compile src/main.py

# Format code (if black is installed)
black src/

# Type check (if mypy is installed)
mypy src/

# Lint code (if flake8 is installed)
flake8 src/
```

## Architecture

The dashboard's layered architecture, callback topology, and the store//relay data path. Moved to [`docs/AGENTS_REFERENCE.md` § Architecture Reference](docs/AGENTS_REFERENCE.md#architecture-reference) — read it when working on this area.

## Demo Mode vs Real Backend

### Demo Mode (Default for Development)

- **Activation:** Set `JUNIPER_CANOPY_DEMO_MODE=1` (the `./demo` script does this automatically)
- **Behavior:** Uses `DemoBackend` with simulated training loop, no real CasCor backend required
- **Use case:** UI development, testing, demonstrations
- **Legacy:** `CASCOR_DEMO_MODE=1` also works but emits a deprecation warning

```bash
# Run in demo mode
./demo
# or explicitly:
export JUNIPER_CANOPY_DEMO_MODE=1
cd src && uvicorn main:app --host 0.0.0.0 --port 8050
```

### Real Backend Mode (Production)

- **Activation:** Do not set `JUNIPER_CANOPY_DEMO_MODE`; configure `JUNIPER_CANOPY_CASCOR_SERVICE_URL`
- **Behavior:** Uses `ServiceBackend` with `CascorServiceAdapter` connecting to real CasCor service
- **Auto-discovery:** Enabled by default; probes `localhost:8200`
- **Use case:** Production, real training sessions

```bash
# Run with real backend (auto-discovery)
cd src && uvicorn main:app --host 0.0.0.0 --port 8050

# Or with explicit service URL
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://cascor-host:8200
cd src && uvicorn main:app --host 0.0.0.0 --port 8050
```

### Agent Guidance for Demo Mode

- **Tests must work with demo mode**: `conftest.py` forces `JUNIPER_CANOPY_DEMO_MODE=1` by default
- **New features must be demo-aware**: The `BackendProtocol` interface ensures both backends expose identical APIs
- **Use `ServiceBackend`/`CascorServiceAdapter` carefully**: Only behind checks that respect demo mode and `CASCOR_BACKEND_AVAILABLE`

## Docker and Local Stack

The container image builds from the **repo-root `Dockerfile`** (the image `juniper-deploy` builds and publishes). Full-stack local orchestration lives in `../juniper-deploy` (Docker Compose for the whole Juniper stack). The legacy `conf/Dockerfile` + `conf/docker-compose.yaml` were removed — they were superseded by `juniper-deploy`.

### Basic Docker Usage

```bash
# Build the image (repo-root Dockerfile)
docker build -t juniper-canopy .

# Run the container -- publish loopback on the host (SEC-F22 posture)
docker run --rm -p 127.0.0.1:8050:8050 juniper-canopy

# Full stack (canopy + cascor + data + redis) via juniper-deploy
cd ../juniper-deploy && docker compose up --build
```

### Agent Guidance for Docker

- Keep ports and environment variables consistent with `app_config.yaml` and `ServerConstants`
- If you change API paths or WebSocket endpoints, update both FastAPI routes and the Docker health checks
- The canonical entrypoint is `python src/main.py` (settings-driven; the SEC-F22 bind guard evaluates `settings.server.host`)—if this changes, update the repo-root `Dockerfile`

## Constants Management

### Using Constants

All application constants are centralized in `src/canopy_constants.py` for maintainability and type safety.

**Import and use constants:**

```python
from canopy_constants import TrainingConstants, DashboardConstants

# Use in your code
max_epochs = TrainingConstants.MAX_TRAINING_EPOCHS
interval = DashboardConstants.FAST_UPDATE_INTERVAL_MS
```

**Available constant classes:**

- `TrainingConstants` - Training parameters (epochs, learning rates, hidden units)
- `DashboardConstants` - UI behavior (update intervals, timeouts, data limits)
- `ServerConstants` - Server configuration (host, port, WebSocket paths, discovery host/ports/timeout, health probe paths)
- `SecurityConstants` - HTTP security headers (CSP, HSTS, X-Frame-Options, etc.), default CSP policy, rate-limit headers, body-limit error messages, exempt paths
- `BackendConstants` - REST endpoint paths, backend adapter timeouts, retry tuning, status keys
- `WebSocketConstants` - WebSocket message types, ping/pong intervals, reconnect backoff
- `JuniperDataConstants` - JuniperData service URL defaults and dataset endpoint paths

**When to use constants:**

✅ Values used in multiple places  
✅ Configuration defaults and limits  
✅ Values that improve code clarity  
❌ Test-specific values (keep in test files)  
❌ Calculated or runtime values  

**Adding new constants:**

See the comprehensive [Constants Guide](docs/cascor/CONSTANTS_GUIDE.md) for detailed instructions on:

- How to add new constants
- Naming conventions (include units: `_MS`, `_S`, `_PX`)
- Constants vs configuration
- Best practices and examples

## Configuration Management

The three-level configuration hierarchy, every setting, and which layer wins. Moved to [`docs/AGENTS_REFERENCE.md` § Configuration Reference](docs/AGENTS_REFERENCE.md#configuration-reference) — read it when working on this area.

## Code Style Guidelines

The standard file header, naming conventions, type-hint and docstring rules. Moved to [`docs/AGENTS_REFERENCE.md` § Code Style Reference](docs/AGENTS_REFERENCE.md#code-style-reference) — read it when working on this area.

## Environment Setup

### Conda Environment

The project uses the live `JuniperCanopy1` conda environment (the name is versioned — discover yours with `conda env list | grep JuniperCanopy`; never activate a `*-DEPRECATED` env):

```bash
# Location
/opt/miniforge3/envs/JuniperCanopy1

# Activate manually
conda activate JuniperCanopy1

# Python interpreter path
/opt/miniforge3/envs/JuniperCanopy1/bin/python
```

> **Env floor-drift guard:** Before serving, run `make check-env` (which runs
> `juniper-env-drift-check --repo-root . --check-lock`) to assert the active
> `JuniperCanopy1` environment and `requirements.lock` still satisfy the
> `juniper-*` floors declared in `pyproject.toml`. This is the local/runtime
> guard for the 2026-06-26 incident class — a live env that drifted below the
> floors while CI stayed green (the same check also runs as a CI preflight in
> the `unit-tests` job). Requires `juniper-ci-tools>=0.5.1`
> (`pip install "juniper-ci-tools>=0.5.1,<0.6.0"`).

### Configuration

Configuration is managed via Pydantic BaseSettings (`src/settings.py`):

1. `JUNIPER_CANOPY_*` environment variables (primary, typed validation)
2. `conf/app_config.yaml` - Legacy YAML configuration
3. `src/canopy_constants.py` - Application defaults

Example:

```bash
export JUNIPER_CANOPY_SERVER__PORT=8051
export JUNIPER_CANOPY_SERVER__DEBUG=true
export JUNIPER_CANOPY_DEMO_MODE=true
```

## Common Issues and Solutions

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'uvicorn'`

**Solution:** Ensure using conda environment's Python:

```bash
# Wrong (uses system Python)
python main.py

# Correct (uses conda Python)
/opt/miniforge3/envs/JuniperCanopy1/bin/python main.py

# Or activate environment first
conda activate JuniperCanopy1
python main.py
```

### Thread Safety Issues

**Problem:** RuntimeError during concurrent access

**Solution:** Use locks for shared state:

```python
with self._lock:
    self.shared_state.append(item)
```

### WebSocket Broadcast Failures

**Problem:** Messages not reaching frontend

**Solution:** Use `broadcast_from_thread` for thread context:

```python
# From thread
websocket_manager.broadcast_from_thread(message)

# From async context
await websocket_manager.broadcast(message)
```

### Demo Mode Won't Stop

**Problem:** Demo continues running after Ctrl+C

**Solution:** Use Event-based stopping:

```python
# In loop
while not self._stop.is_set():
    # ... work
    if self._stop.wait(interval):
        break

# To stop
self._stop.set()
```

## Testing Guidelines

### Testing Requirements

- **No PR without tests** for new/changed behavior
- **Add regression tests** for all fixed bugs
- Place unit tests under `src/tests/unit/`
- Place integration tests under `src/tests/integration/`
- Place performance/smoke tests under `src/tests/performance/`

### Unit Tests

Test individual components in isolation:

```python
def test_demo_mode_thread_safety():
    """Test concurrent access to demo mode state."""
    demo = DemoMode()
    demo.start()

    # Concurrent reads should not raise
    state1 = demo.get_current_state()
    state2 = demo.get_current_state()
    demo.stop()
    assert not demo.is_running
```

### Integration Tests

Test component interactions:

```python
@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Test WebSocket broadcasting from thread."""
    manager = WebSocketManager()
    loop = asyncio.get_running_loop()
    manager.set_event_loop(loop)

    # Test broadcast_from_thread
    manager.broadcast_from_thread({'type': 'test'})
```

### Test Coverage Requirements

- Unit tests: >80% coverage
- Integration tests: Core workflows
- Critical paths: 100% coverage

### PR base-branch guard (required check)

`.github/workflows/pr-base-branch-guard.yml` fails any PR whose base branch is not the
default branch. Its job name -- **`Guard PR base branch`** -- is a **required status check**
in this repo's ruleset, so renaming the job or deleting the file makes `main` unmergeable
until the context is un-required first.

**What it protects against.** A PR based on another feature branch can squash-merge into
that branch, stranding its content off `main` behind a green **MERGED** badge. It has
happened three times in this ecosystem (`juniper-recurrence#7`/`#8`, `juniper-canopy#365`).

**Why it matters more than it looks.** Both rulesets here are scoped to `~DEFAULT_BRANCH`, so
a PR whose base is a feature branch is governed by **no ruleset at all** -- it has zero
required status checks and merges clean with nothing having run:

```bash
gh api repos/pcalnon/<repo>/rules/branches/feature%2Fanything --jq length   # -> 0
gh api repos/pcalnon/<repo>/rules/branches/main               --jq length   # -> 9
```

This workflow carries no `branches:` filter, so it is the **only** check that runs on such a
PR. It cannot block the merge there -- no ruleset applies -- but it turns a silent merge into
a visibly red one.

**If it fails.** Re-open the work against the default branch. The house practice is
**close and re-open** a fresh PR titled `[retarget #NNN]`. Retargeting in place is *not*
sufficient on its own: every `ci*.yml` here uses the default `pull_request` types
`[opened, synchronize, reopened]`, which exclude `edited`, so a retarget re-runs this guard
and nothing else -- the PR stays blocked on its other required contexts until a push or a
close/re-open.

**`stacked-pr` label.** Silences this guard for a deliberate stack. It does **not** make the
PR mergeable into `main`, and it does **not** re-land the stack -- do that separately.

Rollout and rationale: [juniper-ml#434](https://github.com/pcalnon/juniper-ml/issues/434).

## Debugging

### Logging

```python
from logger.logger import get_system_logger, get_training_logger

system_logger = get_system_logger()
system_logger.debug("Detailed information")
system_logger.info("Normal operation")
system_logger.warning("Warning condition")
system_logger.error("Error occurred")
```

### Log Locations

```bash
logs/
├── system.log       # System events
├── training.log     # Training metrics
└── ui.log           # UI interactions
```

### Debug Mode

```bash
# Enable debug logging
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG

# Run with verbose output
/opt/miniforge3/envs/JuniperCanopy1/bin/python -u main.py
```

## Deployment

### Demo Mode, Deployment

```bash
./demo
```

### Production Mode

```bash
# Configure backend (auto-discovery or explicit URL)
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://cascor-host:8200

# Run application
cd src
/opt/miniforge3/envs/JuniperCanopy1/bin/python main.py
```

### Docker

```bash
# Build image (root Dockerfile)
docker build -t juniper-canopy .

# Run container -- publish loopback on the host (SEC-F22 posture)
docker run --rm -p 127.0.0.1:8050:8050 juniper-canopy

# Full stack (canopy + cascor + data + redis) via juniper-deploy
cd ../juniper-deploy && docker compose up --build
```

## API and WebSocket Contracts

Route-by-route REST contracts and the WebSocket message envelope. Moved to [`docs/AGENTS_REFERENCE.md` § API and WebSocket Contract Reference](docs/AGENTS_REFERENCE.md#api-and-websocket-contract-reference) — read it when working on this area.

## Demo Mode Contract

The demo mode must accurately simulate the real CasCor backend to enable UI development without backend dependency. Both `DemoBackend` and `ServiceBackend` implement the same `BackendProtocol` interface.

**Requirements:**

- Produce realistic training loop with pause/resume/reset capabilities
- Match CasCor backend payload shapes, keys, and update cadence
- Expose identical API/WebSocket interfaces via `BackendProtocol` (UI code must be agnostic)
- Support thread-safe control via Events (clean stop/pause)
- Started via `./demo` or `util/juniper_canopy-demo.bash` (conda activation required)

**Implementation:** [src/demo_mode.py](src/demo_mode.py)

**Non-MVP Features (see [DEVELOPMENT_ROADMAP.md](notes/development/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md)):**

- HDF5 snapshot playback
- Export formats (Cytoscape)
- Animated per-weight visualization

## Path and Environment Rules

### Conda Environment, Path and Environment

**Always use the live `JuniperCanopy1` conda environment** (the name is versioned — discover yours with `conda env list | grep JuniperCanopy`):

```bash
# Location
/opt/miniforge3/envs/JuniperCanopy1

# Python interpreter path
/opt/miniforge3/envs/JuniperCanopy1/bin/python
```

**Launch via scripts in `util/`** (they activate conda automatically):

```bash
./demo                    # Demo mode
./util/juniper_canopy-demo.bash     # Same as ./demo
./try                     # Try script (if present)
```

### Path Resolution

**Never use hardcoded absolute paths.** Use `pathlib` and relative resolution:

```python
from pathlib import Path

# Project root (from src/ file)
ROOT = Path(__file__).resolve().parents[1]

# Resolve data directory
data_dir = (ROOT / "data").resolve()
logs_dir = (ROOT / "logs").resolve()
```

### Path and Environment Configuration

**Configuration priority:**

1. Pydantic BaseSettings (`src/settings.py`) with `JUNIPER_CANOPY_*` env vars
2. YAML configuration (`conf/app_config.yaml`) — legacy
3. Constants module (`src/canopy_constants.py`) — defaults

**Example:**

```bash
export JUNIPER_CANOPY_SERVER__PORT=8051
export JUNIPER_CANOPY_SERVER__DEBUG=true
export JUNIPER_CANOPY_DEMO_MODE=true
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/cascor  # Default: ../juniper-cascor
```

## File Placement Rules

Organize files according to their purpose:

| File Type                         | Location                                    | Examples                                                   |
| --------------------------------- | ------------------------------------------- | ---------------------------------------------------------- |
| Source code                       | `src/` and logical subdirs                  | `src/demo_mode.py`, `src/frontend/`                        |
| Tests                             | `src/tests/{unit,integration,performance}/` | `src/tests/unit/test_demo_mode.py`                         |
| Documentation                     | `notes/`                                    | `notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md` |
| Configuration                     | `conf/`                                     | `conf/app_config.yaml`                                     |
| Datasets                          | `data/`                                     | `data/spiral_dataset.csv`                                  |
| Logs                              | `logs/`                                     | `logs/system.log`                                          |
| Images                            | `images/`                                   | `images/network_topology.png`                              |
| Scripts (permanent utilities)     | `util/`                                     | `util/juniper_canopy-demo.bash`                            |
| Scripts (single-use / temp / WIP) | `util/ad-hoc/` (create on first use)        | `util/ad-hoc/YYYY-MM-DD_one-off-cleanup.bash`              |

**Script placement (mandatory)** — `/tmp/` is **prohibited** as the home for any script that produces, modifies, or analyzes repository content. `/tmp/` is reaped when sessions / sandboxes / containers end, and scripts placed there are lost (irrecoverable).

`/tmp/` is still fine as a scratch *workspace* for intermediate artifacts that the script itself creates and reads — the prohibition is on script *source files*, not on transient data.

This is an ecosystem-wide rule restated in the parent `Juniper/AGENTS.md` "Cross-Project Conventions" section. See [`util/ad-hoc/README.md`](util/ad-hoc/README.md) for the per-script convention (file-header requirements, graduation lifecycle). Motivating incident: irrecoverable loss of `phase4_consolidate.py` and `v2_citation_validate.py` from the juniper-ml requirements-snapshot effort.

**Mirror package structure in tests:**

```bash
src/demo_mode.py           -> src/tests/unit/test_demo_mode_*.py
src/communication/         -> src/tests/unit/test_websocket_*.py
```

## Documentation Organization

How the documentation set is organised: which tree holds what, and why. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation Organization](docs/DOCUMENTATION_OVERVIEW.md#documentation-organization) — read it when working on this area.

## Documentation Maintenance Workflow

The end-to-end workflow for keeping documentation current as the code moves. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation Maintenance Workflow](docs/DOCUMENTATION_OVERVIEW.md#documentation-maintenance-workflow) — read it when working on this area.

## Documentation Standards

House style for authoring docs: headings, anchors, code samples, and link forms. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation Authoring Standards](docs/DOCUMENTATION_OVERVIEW.md#documentation-authoring-standards) — read it when working on this area.

## Documentation File Types

Every documentation file type, what belongs in it, and where it lives. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation File Types](docs/DOCUMENTATION_OVERVIEW.md#documentation-file-types) — read it when working on this area.

## Update Triggers

Which code changes oblige a documentation update, and which document each one touches. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation Update Triggers](docs/DOCUMENTATION_OVERVIEW.md#documentation-update-triggers) — read it when working on this area.

## Archive Procedures

How superseded documentation is archived under `docs/history/` without breaking links. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Archive Procedures](docs/DOCUMENTATION_OVERVIEW.md#archive-procedures) — read it when working on this area.

## [Unreleased]

### Changed

- Split testing documentation into focused guides for better navigation
  - Archived: TESTING_GUIDE_CONSOLIDATED.md → docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md
  - Created: TESTING_QUICK_START.md, TESTING_MANUAL.md, TESTING_REFERENCE.md,
    TESTING_ENVIRONMENT_SETUP.md, TESTING_REPORTS_COVERAGE.md

### Maintaining Archive Integrity

**Archive Index Structure:**

`notes/history/INDEX.md` should maintain chronological organization:

```markdown
# Documentation Archive Index

This directory contains historical documentation that has been superseded or consolidated.

## 2025-11-05: API Reference v2 Migration

- **[API_REFERENCE_v1_2025-11-05.md](API_REFERENCE_v1_2025-11-05.md)**
  - Version 1.x API documentation
  - Replaced by: [API_REFERENCE.md](../API_REFERENCE.md) (v2)

## 2025-11-04: Testing Documentation Split

- **[TESTING_GUIDE_CONSOLIDATED_2025-11-04.md](TESTING_GUIDE_CONSOLIDATED_2025-11-04.md)**
  - Consolidated testing guide
  - Replaced by: Split testing documentation (see above)

## 2025-11-04: Backend Integration Reorganization

- **[BACKEND_INTEGRATION_2025-11-04.md](BACKEND_INTEGRATION_2025-11-04.md)**
  - Generic backend integration guide
  - Replaced by: CASCOR_BACKEND_MANUAL.md with specific integration details

## Archive Navigation

- Latest documentation: [Documentation Overview](../DOCUMENTATION_OVERVIEW.md)
- Changelog: [CHANGELOG.md](../CHANGELOG.md)
```

## Documentation Update Workflow

The per-change checklist for updating documentation alongside a code change. Moved to [`docs/DOCUMENTATION_OVERVIEW.md` § Documentation Update Workflow](docs/DOCUMENTATION_OVERVIEW.md#documentation-update-workflow) — read it when working on this area.

## Definition of Done

All new or modified code must meet these requirements before merging:

### Code Quality at Completion

- [ ] Thread safety preserved (locks/events for shared state)
- [ ] Bounded collections for streaming/history buffers (no memory leaks)
- [ ] Metric naming follows standard (snake_case, train_/val_ prefixes)
- [ ] Proper path resolution (no hardcoded paths, use pathlib)
- [ ] Error handling with appropriate logging level

### Testing Status at Completion

- [ ] Unit tests added for new functionality
- [ ] Integration tests for component interactions
- [ ] Regression tests for fixed bugs
- [ ] Coverage maintained/increased (>80% unit; 100% critical paths)
- [ ] All tests passing: `pytest`

### API/Interface Stability

- [ ] API/WebSocket changes backward compatible or versioned
- [ ] Payload schemas documented in code docstrings
- [ ] No breaking changes to existing contracts without migration plan

### Documentation at Completion

- [ ] [CHANGELOG.md](CHANGELOG.md) updated with changes and impact
- [ ] [README.md](README.md) reflects current run/test instructions
- [ ] [notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](notes/development/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md) status updated
- [ ] Code comments only where complexity requires explanation
- [ ] All public methods have docstrings

### Verification of Completion

- [ ] No syntax errors: `python -m py_compile src/**/*.py`
- [ ] No import errors when running application
- [ ] No regressions in existing functionality

## Contributing

### Before Committing

1. Run tests: `pytest`
2. Check syntax: `python -m py_compile src/**/*.py`
3. Verify imports work
4. Update documentation (CHANGELOG, README, ROADMAP)
5. Verify Definition of Done checklist complete

### Code Review Checklist

- [ ] Thread safety for concurrent code
- [ ] Bounded collections (no memory leaks)
- [ ] Error handling with appropriate logging
- [ ] Tests added/updated (no PR without tests)
- [ ] Documentation updated
- [ ] No hardcoded paths or credentials

## Additional Resources

- Juniper Ecosystem Guide: see `../CLAUDE.md` (parent directory)
- CasCor Repository: see `../juniper-cascor/`
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Dash Documentation](https://dash.plotly.com/)
- [WebSocket RFC](https://tools.ietf.org/html/rfc6455)

## MCP Server Availability

The project includes MCP (Model Context Protocol) server configuration for AI-assisted development:

- **`.mcp.json`** - MCP server configuration (Exa API integration)
- **`notes/mcp/`** - Setup guides:
  - `claude-code-serena-setup-guide.md` - Serena MCP setup for semantic code analysis
  - `claude-code-alphavantage-setup-guide.md` - AlphaVantage API setup
  - `EXA_API_REFERENCE.md` - Exa search API reference

---

## Worktree Procedures

> **OPERATING INSTRUCTION**: All feature, bugfix, and task work SHOULD use git worktrees for isolation.

Full procedures are defined in:

- **`notes/WORKTREE_SETUP_PROCEDURE.md`** — Creating a worktree for a new task
- **`notes/WORKTREE_CLEANUP_PROCEDURE_V2.md`** — Merging, removing, and pushing after task completion

Worktrees are centralized in `/home/pcalnon/Development/python/Juniper/worktrees/`. See the parent `CLAUDE.md` for the full cross-project worktree standard.

---

## Recent Changes

See `git log --oneline -20` and [CHANGELOG.md](CHANGELOG.md) for recent changes.

<!-- Historical session log (2025-10 through 2026-02) removed — content was obsolete
     with broken links to relocated/deleted files. Consult git history for details. -->

## WebSocket Message Schema

<!-- Historical session log deleted — see git history for details -->

All WebSocket messages follow a standardized schema for consistency. See `src/communication/websocket_manager.py` for detailed documentation and message builder functions.

### Message Format

```json
{
  "type": "state | metrics | topology | event | control_ack",
  "timestamp": 1700000000.123,
  "data": {
    // Type-specific payload
  }
}
```

### Message Types

- **state**: Training state updates (status, phase, learning_rate, current_epoch, etc.)
- **metrics**: Training metrics (loss, accuracy, validation metrics)
- **topology**: Network architecture (nodes, connections, unit counts)
- **event**: Training events (cascade_add, status_change, phase_change)
- **control_ack**: Control command responses (success/failure acknowledgments)

### Using Message Builders

Always use the standardized message builder functions from `communication.websocket_manager`:

```python
from communication.websocket_manager import (
    create_state_message,
    create_metrics_message,
    create_topology_message,
    create_event_message,
    create_control_ack_message,
    websocket_manager
)

# Example: Broadcasting metrics
metrics_msg = create_metrics_message({"epoch": 42, "metrics": {...}})
websocket_manager.broadcast_from_thread(metrics_msg)
```

See the module docstring in `src/communication/websocket_manager.py` for complete examples and detailed schema documentation.

---

## Thread Handoff (Mandatory — Replaces Thread Compaction)

> **CRITICAL OPERATING INSTRUCTION**: Thread handoff MUST be performed instead of thread compaction. This section defines mandatory behavior that overrides Claude Code's default compaction process.

### What This Is

When a long-running conversation approaches context limits, Claude Code normally performs **thread compaction** — summarizing prior context to free token capacity. This introduces information loss. Instead, Claude Code instances working on this project MUST perform a **proactive thread handoff**: transferring a curated, high-signal summary to a fresh thread with full context capacity.

The full handoff protocol is defined in **`notes/THREAD_HANDOFF_PROCEDURE.md`**. Read that file when a handoff is triggered.

### When to Trigger a Handoff

**Automatic trigger (pre-compaction threshold):** Initiate a thread handoff when token utilization reaches **95% to 99%** of the level at which thread compaction would normally be triggered. This means the handoff fires when you are within **1% to 5%** of the compaction threshold, ensuring the handoff completes before compaction would occur.

Concretely:

- If compaction would trigger at N% context utilization, begin handoff at (N − 5)% to (N − 1)%.
- **Self-assessment rule**: At each turn where you are performing multi-step work, assess whether you are approaching the compaction threshold. If you estimate you are within 5% of it, begin the handoff protocol immediately.
- When the system compresses prior messages or you receive a context compression notification, treat this as a signal that handoff should have already occurred — immediately initiate one.

**Additional triggers** (from `notes/THREAD_HANDOFF_PROCEDURE.md`):

| Condition                   | Indicator                                                            |
| --------------------------- | -------------------------------------------------------------------- |
| **Context saturation**      | Thread has performed 15+ tool calls or edited 5+ files               |
| **Phase boundary**          | A logical phase of work is complete                                  |
| **Degraded recall**         | Re-reading a file already read, or re-asking a resolved question     |
| **Multi-module transition** | Moving between major components                                      |
| **User request**            | User says "hand off", "new thread", or similar                       |

**Do NOT handoff** when:

- The task is nearly complete (< 2 remaining steps)
- The current thread is still sharp and producing correct output
- The work is tightly coupled and splitting would lose critical in-flight state

### How to Execute a Handoff

1. **Checkpoint**: Inventory what was done, what remains, what was discovered, and what files are in play
2. **Compose the handoff goal**: Write a concise, actionable summary (see templates in `notes/THREAD_HANDOFF_PROCEDURE.md`)
3. **Present to user**: Output the handoff goal to the user and recommend starting a new thread with that goal as the initial prompt
4. **Include verification commands**: Always specify how the new thread should verify its starting state (test commands, file checks)
5. **State git status**: Mention branch, staged files, and any uncommitted work

### Rules

- **This is not optional.** Every Claude Code instance on this project must follow these rules.
- **Handoff early, not late.** A handoff at 70% context usage is better than compaction at 95%.
- **Do not duplicate CLAUDE.md content** in the handoff goal — the new thread reads CLAUDE.md automatically.
- **Be specific** in the handoff goal: include file paths, decisions made, and test status.
