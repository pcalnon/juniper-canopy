# AGENTS Reference — juniper-canopy

**Project**: juniper-canopy — Real-Time Monitoring Dashboard for Juniper
**Author**: Paul Calnon
**License**: MIT License
**Last Updated**: 2026-09-04

Reference material relocated **verbatim** out of `AGENTS.md` under the shared-session-memory plan
(juniper-ml plan §P5 step e). `AGENTS.md` is loaded into every session; this file is read on demand.
Nothing here was rewritten — each section carries a provenance line naming where it came from.

**Hazards are deliberately NOT here.** Directives whose *non-application destroys work* stay
resident in [`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate), because a
pointer only helps an agent that already knows to look.

---

## Table of Contents

- [Architecture Reference](#architecture-reference)
- [Hierarchy Depth Filter (CAN-020)](#hierarchy-depth-filter-can-020)
- [Configuration Reference](#configuration-reference)
- [API and WebSocket Contract Reference](#api-and-websocket-contract-reference)
- [Further Reading](#further-reading)

---

## Architecture Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Directory Structure

```bash
juniper_canopy/
├── conf/                         # Configuration & infrastructure
│   ├── app_config.yaml           # Main application config (YAML layer)
│   ├── layouts/                  # Dashboard layout definitions
│   │   └── metrics_layouts.json  # Metrics panel layout config
│   ├── conda_environment.yaml    # Conda env spec
│   ├── conda_environment_ci.yaml # CI-specific conda env
│   ├── requirements.txt          # Pip dependencies
│   ├── requirements_ci.txt       # CI pip dependencies
│   ├── Dockerfile                # Container image for Juniper Canopy
│   ├── docker-compose.yaml       # Local stack (app + services like Redis)
│   ├── logging_config.yaml       # Logging configuration
│   ├── logging_colors.conf       # Color output configuration
│   ├── init.conf                 # Shared shell init for utility scripts
│   └── ... (60+ shell/logging/env configs)
├── data/                         # Datasets for training/testing
├── docs/                         # Reference & subsystem documentation
│   ├── api/                      # API schema and reference docs
│   ├── cascor/                   # CasCor backend integration docs
│   ├── cassandra/                # Cassandra integration docs
│   ├── ci_cd/                    # CI/CD pipeline documentation
│   ├── demo/                     # Demo mode behavior & usage
│   ├── deployment/               # Kubernetes deployment plan
│   ├── history/                  # Archived/superseded documentation
│   ├── redis/                    # Redis/cache integration docs
│   ├── testing/                  # Testing guides and advanced scenarios
│   └── *.md                      # Quick start, environment setup, reference, etc.
├── images/                       # Generated images/screenshots
├── logs/                         # Log files (runtime)
├── notes/                        # Development notes and implementation details
│   ├── analysis/                 # Technical analyses
│   ├── development/              # Dev roadmaps and phase work
│   ├── fixes/                    # Bug fix plans and reports
│   ├── history/                  # Historical analyses and audits
│   ├── integration/              # Integration phase analysis (phases 0-5)
│   ├── mcp/                      # MCP server setup guides
│   ├── pull_requests/            # PR descriptions
│   ├── releases/                 # Release notes (v0.14.0+)
│   ├── research/                 # Research proposals
│   └── templates/                # Issue, PR, release note templates
├── reports/                      # Test coverage and CI reports
├── scripts/                      # Service management scripts
│   ├── generate_dep_docs.sh      # Dependency documentation generator
│   ├── juniper-canopy.service    # Systemd service file
│   └── juniper-ctl               # Service control utility
├── src/                          # Source code
│   ├── backend/                  # CasCor backend integration & adapters
│   │   ├── __init__.py           # Backend factory (create_backend)
│   │   ├── protocol.py           # BackendProtocol typing interface
│   │   ├── demo_backend.py       # DemoBackend (wraps DemoMode)
│   │   ├── service_backend.py    # ServiceBackend (wraps CascorServiceAdapter)
│   │   ├── cascor_service_adapter.py # juniper-cascor-client wrapper
│   │   ├── circuit_breaker.py    # Fault tolerance
│   │   ├── cassandra_client.py   # Optional Cassandra integration
│   │   ├── redis_client.py       # Optional Redis caching
│   │   ├── data_adapter.py       # Data normalization
│   │   ├── training_monitor.py   # Metrics collection (TrainingState)
│   │   ├── training_state_machine.py # FSM for training control
│   │   ├── state_sync.py         # State synchronization
│   │   └── statistics.py         # Statistics module
│   ├── communication/            # WebSocket management & protocol
│   │   └── websocket_manager.py  # WebSocket connection and broadcast management
│   ├── frontend/                 # Dash dashboard components & callbacks
│   │   ├── dashboard_manager.py  # DashboardManager orchestrator
│   │   ├── base_component.py     # BaseComponent for UI modules
│   │   ├── callback_context.py   # Callback context utilities
│   │   ├── tooltips.py           # UI tooltips
│   │   └── components/           # Individual UI panel components
│   │       ├── about_panel.py
│   │       ├── candidate_metrics_panel.py
│   │       ├── cassandra_panel.py
│   │       ├── dataset_plotter.py
│   │       ├── decision_boundary.py
│   │       ├── hdf5_snapshots_panel.py
│   │       ├── metrics_panel.py
│   │       ├── network_visualizer.py
│   │       ├── parameters_panel.py
│   │       ├── redis_panel.py
│   │       ├── training_metrics.py
│   │       ├── tutorial_panel.py
│   │       └── worker_panel.py
│   ├── logger/                   # Logging system
│   │   └── logger.py             # Structured JSON/text logging
│   ├── tests/                    # Test suite
│   │   ├── unit/                 # Unit tests (fast, no external deps)
│   │   │   ├── backend/          # Backend component unit tests
│   │   │   └── frontend/         # Frontend component unit tests
│   │   ├── integration/          # Integration tests (DB, files, backend)
│   │   │   └── backend/          # Backend integration tests
│   │   ├── regression/           # Regression tests for fixed bugs
│   │   ├── performance/          # Performance/benchmark tests
│   │   ├── fixtures/             # Additional test fixtures
│   │   ├── mocks/                # Mock implementations
│   │   ├── data/                 # Test data generators
│   │   └── helpers/              # Test utility functions
│   ├── main.py                   # FastAPI + Dash application entrypoint
│   ├── settings.py               # Pydantic BaseSettings configuration (primary)
│   ├── config_manager.py         # Legacy YAML-based configuration (deprecated)
│   ├── canopy_constants.py       # Central constants (see "Constants Management")
│   ├── demo_mode.py              # Demo mode simulation
│   ├── discovery.py              # Auto-discovery of cascor instances
│   ├── health.py                 # Health check probes (/v1/health/*)
│   ├── middleware.py             # Security, rate limiting, CSP headers
│   ├── observability.py          # Sentry, Prometheus, request ID middleware
│   ├── security.py               # API key authentication, rate limiting
│   └── secrets_util.py           # Environment secret management
├── util/                         # Utility scripts (bash, invoked via ./demo, etc.)
│   └── verification/             # Verification helper scripts
├── .env.dev                      # Development environment variables
├── .env.example                  # Example environment template
├── .env.prod                     # Production environment variables
├── .mcp.json                     # MCP server configuration
├── AGENTS.md                     # This file
├── CHANGELOG.md                  # Chronological change history
├── CLAUDE.md -> AGENTS.md        # Symlink for Claude Code
├── Dockerfile                    # Root-level container image
├── LICENSE                       # MIT License
├── README.md                     # Project overview
├── conftest.py                   # Root pytest config (adds src/ to path)
├── demo                          # Symlink -> util/juniper_canopy-demo.bash
├── pyproject.toml                # Python project config (black, isort, pytest, coverage)
├── requirements.lock             # Locked dependencies
└── try                           # Symlink -> util/juniper_canopy.bash
```

### Key Components

1. **FastAPI Backend** (`src/main.py`)
   - RESTful API endpoints (30+ routes)
   - WebSocket endpoints for real-time communication (`/ws/training`, `/ws/control`, `/ws`)
   - Dash app integration via WSGI middleware (`a2wsgi`)
   - Async lifespan manager for startup/shutdown orchestration

2. **Pydantic Settings** (`src/settings.py`)
   - Primary configuration via `JUNIPER_CANOPY_*` env vars
   - Typed, validated settings with nested model hierarchy
   - Legacy `CASCOR_*` fallback with deprecation warnings
   - See [Configuration Management](../AGENTS.md#configuration-management) for details

3. **Dash Dashboard** (`src/frontend/dashboard_manager.py`)
   - `DashboardManager` orchestrates all UI components
   - 13 specialized panel components in `frontend/components/`
   - Interactive real-time plotting via Plotly/Dash callbacks
   - **Training counter semantics (Step / Epoch / Iteration / Hidden Units).** The
     header, Network Info panel and metrics tiles render cascor's training counters,
     whose meanings are the **C2b contract** (single source of truth: juniper-cascor
     [`docs/api/JUNIPER_CASCOR_API_REFERENCE.md`](https://github.com/pcalnon/juniper-cascor/blob/main/docs/api/JUNIPER_CASCOR_API_REFERENCE.md)
     — "Counter semantics (C2b)"; reconciled in cascor#400). Do not conflate them:
     `current_epoch`/`current_step` = completed **training steps** (one initial output
     pass + one per growth iteration), rendered "Step" — **not** an inner epoch;
     `grow_iteration`/`grow_max` = the true growth **"Iteration"** (vs `max_iterations`),
     distinct from the hidden-unit count; `hidden_units`/`max_hidden_units` = installed
     units vs capacity; `output_epoch`/`candidate_epoch` (+ `*_total_epochs`) = the
     phase-qualified within-pass **"Epoch"** (resets to 0 at each phase entry by design);
     `max_epochs` = the **derived display budget** (`output_epochs + min(max_iterations,
     max_hidden_units) * (candidate_epochs + output_epochs)`), surfaced as the Parameters
     panel's "Maximum Total Epochs" — **not** an `Epoch: X / Y` fraction against the step
     counter (different units). `DashboardManager._counter_displays()` is the shared
     mapping helper; regressions live in `src/tests/unit/frontend/test_n6_counter_semantics.py`.

4. **Backend Protocol & Factory** (`src/backend/protocol.py`, `src/backend/__init__.py`)
   - `BackendProtocol` defines the typing interface for all backends
   - Factory function `create_backend()` selects DemoBackend or ServiceBackend based on settings
   - Dependency injection pattern for testability

5. **Service Backend** (`src/backend/service_backend.py`, `src/backend/cascor_service_adapter.py`)
   - `ServiceBackend` wraps `CascorServiceAdapter` for production use
   - `CascorServiceAdapter` uses `juniper-cascor-client` for REST/WebSocket communication
   - Circuit breaker pattern for fault tolerance (`src/backend/circuit_breaker.py`)
   - State synchronization with remote cascor (`src/backend/state_sync.py`)

6. **Demo Backend** (`src/backend/demo_backend.py`, `src/demo_mode.py`)
   - `DemoBackend` wraps `DemoMode` for offline development
   - Simulated CasCor training loop with realistic metrics
   - Thread-safe operation via locks and events

7. **Training State Machine** (`src/backend/training_state_machine.py`, `src/backend/training_monitor.py`)
   - FSM for training command validation (START, STOP, PAUSE, RESUME, RESET)
   - `TrainingPhase` enum: IDLE, OUTPUT, CANDIDATE, INFERENCE
   - `TrainingStatus` enum: STOPPED, STARTED, PAUSED, COMPLETED, FAILED
   - Thread-safe global state tracking via `TrainingState`

8. **WebSocket Manager** (`src/communication/websocket_manager.py`)
   - Connection management with heartbeat
   - Thread-safe broadcasting via `broadcast_from_thread()`
   - Message builder functions for standardized schemas

9. **Health & Observability** (`src/health.py`, `src/observability.py`)
   - Health check probes: `/v1/health`, `/v1/health/live`, `/v1/health/ready`
   - Dependency probing (JuniperData, CasCor availability)
   - Sentry integration, Prometheus metrics, request ID middleware

10. **Infrastructure Clients** (`src/backend/redis_client.py`, `src/backend/cassandra_client.py`)
    - Optional Redis caching (soft-fail if not installed)
    - Optional Cassandra time-series storage (soft-fail if not installed)
    - Status endpoints for monitoring

11. **Security & Middleware** (`src/security.py`, `src/middleware.py`)
    - API key authentication
    - Rate limiting
    - CSP headers, CORS configuration

12. **Constants Module** (`src/canopy_constants.py`)
    - Centralized application constants
    - Type-safe configuration values
    - Training parameters, UI settings, server config

---

## Hierarchy Depth Filter (CAN-020)

Operator surface: the Network Topology tab's **Hidden depth** slider
(`network-visualizer-depth-slider`). Developer contract below. User-facing
copy lives in [`USER_MANUAL.md` § Network Topology Tab](USER_MANUAL.md#network-topology-tab).

### Intent

CasCor cascade order *is* the hierarchy: `hidden_0` was added first,
`hidden_N-1` most recently. The slider keeps the first `K` hidden units
(and any edge that touches a dropped unit) so a deep cascade can be read
one prefix at a time. It is a **view filter** — it does not change the
backend network.

The control is hidden until `topology.hidden_units >= 1`. Slider `max`
tracks the live hidden-unit count clientside; a user-picked `K` persists
across `cascade_add` as long as it is still in range, otherwise it snaps
to the new max (show all).

### Filter contract

`NetworkVisualizer._apply_hierarchy_filter(topology, depth, n_hidden_total)`
is the oracle. It never mutates the input dict (that payload is a Dash
store other callbacks also read). No-op arms return the original
reference and label `"all"`:

| `depth` / `n_hidden_total` | Graph | Label |
| --- | --- | --- |
| `depth is None` | unchanged | `"all"` |
| `depth <= 0` | unchanged | `"all"` |
| `depth >= n_hidden_total` | unchanged | `"all"` |
| `n_hidden_total == 0` | unchanged | `"all"` |
| `0 < depth < n_hidden_total` | `hidden_units` capped at `depth`; drop any edge whose `from`/`to` is `hidden_K` with `K >= depth` | `"{depth} of {n_hidden_total}"` |

Unparseable node ids (`hidden_x`) are kept — the filter cannot decide.

**`0` means "no filter", not "show zero units."** The slider ships
`min=0, max=0, value=0`. Treating rest-state `0` as a real depth would
blank the graph. The same rest state is why a label that only special-
cases `v === nHidden` reads `"0 of 40"` while all 40 units are drawn.

The filter runs inside `update_network_graph` **before** `compute_hash`,
so a depth change invalidates the figure cache. That callback is the
starvation-prone rebuild (measured **1.5–31 s**; F-CANOPY-037 / -039 /
-043). Do not add `-depth-label.children` as a ninth Output of it —
the number under the thumb would lag the drag by seconds, and two of
the four return paths are empty-figure exits with no meaningful label.

### Label wiring (F-CANOPY-042)

Two defects, one finding id.

**Defect A — State vs Input.** On `main` the label is the fourth Output
of the clientside slider-bounds sync. That callback's only Input is
`-topology-store.data`; `-depth-slider.value` rides as **State**. A
State is read when something *else* fires, so moving the slider
recomputes nothing. Since canopy#542 identity-suppressed the topology
store, at idle the label never updates at all.

The obvious repair is structurally unavailable: adding
`Input(-depth-slider, "value")` to that callback makes one
component-property both an Input and an Output of a single callback,
which Dash rejects at registration as a circular dependency. The
bounds-sync callback **must** keep writing `max` and `value` (it bumps
`max` on grow and snaps an out-of-range pick). Therefore the label
cannot live there.

**Defect B — two meanings of `0`.** The filter's `depth <= 0` arm is
`"all"`. The old clientside rule was `(v === nHidden) ? "all" : v + " of " + nHidden`.
On a loaded 40-unit network the control reads `"0 of 40"` while all 40
units are displayed, before anyone touches anything. Fixing the wiring
alone does not fix this.

**Incoming repair (canopy#570, not yet on `main`):** a second clientside
callback owns `-depth-label.children` with Inputs
`[-depth-slider.value, -topology-store.data]` — both operands of the
filter, because a grow event changes the denominator with no user
action. The JavaScript guard is a condition-for-condition
transliteration of `_apply_hierarchy_filter`. The bounds-sync callback
returns three elements (`max`, `value`, container `style`). Until #570
merges, the `main` tree still has Defect A and Defect B.

### Dual definition — change one, change both

`_apply_hierarchy_filter` still *returns* the label. The rebuild
discards it on purpose so the readout is not stuck behind the 1.5–31 s
paint. That return value stays the definition the clientside rule
transliterates. A label that says `"0 of 40"` while the filter returns
the unfiltered topology is exactly F-CANOPY-042. Edit the Python guard
and the JavaScript guard in the same change.

### Tests

On `main`:

```bash
cd src
pytest tests/unit/test_network_visualizer.py -k "Hierarchy or hierarchy or depth" -v
```

`TestHierarchyDepthFilter` drives the Python oracle directly (None / 0 /
at-total / above-total / keep-3 / drop-edges / no-mutate /
malformed-id). `TestHierarchyDepthSliderWiring` is source-level only —
it does not execute the clientside function.

The #570 suite (`src/tests/unit/frontend/test_f042_depth_filter_label.py`,
not on `main` yet) asserts wiring against `app._callback_list` after a
real `register_callbacks`, executes the registered JavaScript under
`node` over a 48-case grid with `_apply_hierarchy_filter` as the oracle,
and pins that no callback has `-depth-slider.value` as both Input and
Output. Do not replace that shape with a test that re-types the
production expression and asserts against its own copy — that class let
F-CANOPY-041b and F-CANOPY-045 ship green.

E2E rows M-TOPOLOGY-06 / M-TOPOLOGY-07 live in juniper-ml. The old
M-TOPOLOGY-06 predicate was `label == want OR counts["hidden"] == want`
and passed on the counts branch while the label stayed `"0 of 40"`.
M-TOPOLOGY-07 recorded the label but scored `display` alone.

### Pitfalls

- Do not merge the label back into the bounds-sync callback. Dash will
  refuse the registration (or a future "simplification" will silently
  restore Defect A).
- Do not route the label through `update_network_graph`. Correct by
  construction, unusable under the thumb.
- Do not treat slider `value=0` as "show zero hidden units."
- Do not mutate the topology dict inside the filter.
- Count writers by grepping the store / component id, not by reading
  the handler you happened to open (`allow_duplicate` and a split
  clientside callback are both easy to miss). Same lesson as the
  `metrics-panel-metrics-store` hazard in `AGENTS.md`.

---

## Configuration Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Configuration Hierarchy

The juniper_canopy application uses a three-level configuration hierarchy (highest to lowest priority):

1. **Pydantic BaseSettings** (`src/settings.py`) - `JUNIPER_CANOPY_*` environment variables with typed validation
2. **YAML Configuration** (`conf/app_config.yaml`) - Deployment-specific settings (legacy)
3. **Constants Module** (`src/canopy_constants.py`) - Application defaults

> **Note**: The previous `CASCOR_*` environment variable prefix is deprecated but still supported with deprecation warnings. All new code should use `JUNIPER_CANOPY_*`.

### Pydantic Settings (Primary)

The `Settings` class in `src/settings.py` provides typed, validated configuration:

```python
from settings import get_settings

settings = get_settings()
host = settings.server.host       # "127.0.0.1"
port = settings.server.port       # 8050
demo = settings.demo_mode         # False
```

### Environment Variable Overrides

All configuration values can be overridden via environment variables with the `JUNIPER_CANOPY_` prefix. Nested settings use double-underscore (`__`) as delimiter.

#### Server Configuration

```bash
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0      # Server bind address (default: 127.0.0.1)
export JUNIPER_CANOPY_SERVER__PORT=8051          # Server port (default: 8050)
export JUNIPER_CANOPY_SERVER__DEBUG=true         # Debug mode (default: false)
```

#### Training Parameters

```bash
export JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=300          # Default epochs (default: 1000000)
export JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT=0.02  # Learning rate (default: 0.01)
export JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT=500    # Max hidden units (default: 1000)
```

#### Backend Integration

```bash
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/cascor  # CasCor backend path (default: ../juniper-cascor)
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://localhost:8200  # CasCor service URL
export JUNIPER_CANOPY_JUNIPER_DATA_URL=http://localhost:8100    # JuniperData service URL
```

#### CasCor Auto-Discovery

```bash
export JUNIPER_CANOPY_CASCOR_DISCOVERY__ENABLED=true          # Enable auto-discovery (default: true)
export JUNIPER_CANOPY_CASCOR_DISCOVERY__HOST=localhost         # Discovery host (default: localhost)
export JUNIPER_CANOPY_CASCOR_DISCOVERY__PORTS=[8200]           # Ports to probe (default: [8200])
export JUNIPER_CANOPY_CASCOR_DISCOVERY__TIMEOUT_SECONDS=2.0   # Probe timeout (default: 2.0)
```

#### WebSocket Configuration

```bash
export JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS=100      # Max concurrent connections (default: 50)
export JUNIPER_CANOPY_WEBSOCKET__HEARTBEAT_INTERVAL=60    # Heartbeat interval in seconds (default: 30)
export JUNIPER_CANOPY_WEBSOCKET__RECONNECT_ATTEMPTS=10    # Reconnection attempts (default: 5)
export JUNIPER_CANOPY_WEBSOCKET__RECONNECT_DELAY=5        # Delay between reconnects (default: 2)
```

#### Demo Mode

```bash
export JUNIPER_CANOPY_DEMO_MODE=true             # Enable demo mode (default: false)
export JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL=0.5   # Simulation step interval (default: 1.0)
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=40      # Add hidden unit every N epochs (default: 30)
```

#### Logging & Observability

```bash
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG             # Log level (default: INFO)
export JUNIPER_CANOPY_LOG_FORMAT=json             # Log format: text or json (default: text)
export JUNIPER_CANOPY_SENTRY_DSN=https://...      # Sentry DSN for error tracking (default: unset)
export JUNIPER_CANOPY_METRICS_ENABLED=true        # Enable Prometheus metrics (default: false)
```

#### Rate Limiting & CORS

```bash
export JUNIPER_CANOPY_RATE_LIMIT_ENABLED=true                  # Enable rate limiting (default: false)
export JUNIPER_CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE=120       # Requests per minute (default: 60)
export JUNIPER_CANOPY_CORS_ORIGINS='["http://localhost:3000"]'  # Allowed CORS origins (default: [])
```

#### Shared / Cross-Service Variables

```bash
export JUNIPER_DATA_URL=http://localhost:8100       # JuniperData URL (shared, no prefix)
export JUNIPER_DATA_API_KEY=your-api-key            # JuniperData API key
export JUNIPER_CASCOR_API_KEY=your-api-key          # CasCor API key
export CANOPY_API_KEY=your-api-key                  # Canopy API key (disables /docs if set)
```

### Legacy CASCOR_* Environment Variables

The following legacy variables are supported with deprecation warnings:

| Legacy Variable | New Variable | Notes |
|----------------|-------------|-------|
| `CASCOR_DEMO_MODE` | `JUNIPER_CANOPY_DEMO_MODE` | Boolean flag |
| `CASCOR_BACKEND_PATH` | `JUNIPER_CANOPY_BACKEND_PATH` | Path to cascor |
| `CASCOR_SERVICE_URL` | `JUNIPER_CANOPY_CASCOR_SERVICE_URL` | Service URL |

If both legacy and new variables are set, the new `JUNIPER_CANOPY_*` variable takes precedence.

### YAML Configuration (Secondary)

Configuration file location: `conf/app_config.yaml`

The YAML configuration is a secondary layer used by the legacy `ConfigManager`. New settings should be added to `settings.py` instead.

### Using Configuration in Code

```python
from settings import get_settings
from canopy_constants import ServerConstants

# Primary: use Pydantic Settings
settings = get_settings()
host = settings.server.host       # Typed, validated
port = settings.server.port

# Constants: for values not in Settings
default_host = ServerConstants.DEFAULT_HOST
```

### Configuration Best Practices

1. **Use Pydantic Settings**: Add new config to `settings.py`, not `config_manager.py`
2. **Validate via type system**: Pydantic handles validation automatically
3. **Use the `JUNIPER_CANOPY_` prefix**: All new env vars must use this prefix
4. **Double-underscore for nesting**: `JUNIPER_CANOPY_SERVER__PORT=8051`
5. **Document all overrides**: Comment why environment variables are being set

### Testing Configuration

```bash
# Run configuration tests
cd src
pytest tests/unit/test_config_refactoring.py -v          # Unit tests
pytest tests/integration/test_config_integration.py -v   # Integration tests

# Test with environment variable overrides
export JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=500
export JUNIPER_CANOPY_SERVER__PORT=8051
./demo
# Verify dashboard shows updated settings

# Validate Settings loading
python -c "from settings import get_settings; s = get_settings(); print(f'port={s.server.port}')"
```

### Configuration Troubleshooting

**Problem**: Environment variable not taking effect

**Solution**: Check variable name and nesting delimiter

```bash
# Correct (new prefix with double-underscore nesting)
export JUNIPER_CANOPY_SERVER__PORT=8051

# Incorrect (single underscore — not nested)
export JUNIPER_CANOPY_SERVER_PORT=8051

# Legacy (still works but deprecated)
export CASCOR_SERVER_PORT=8051
```

**Problem**: Configuration value seems wrong

**Solution**: Check which settings layer is being used

```bash
# Inspect resolved settings
python -c "from settings import get_settings; s = get_settings(); print(s.model_dump())"
```

**Problem**: YAML configuration not loading

**Solution**: Verify YAML syntax and file location

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"
```

---

## API and WebSocket Contract Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### REST API Endpoints

All REST endpoints defined in [src/main.py](../src/main.py) and [src/health.py](../src/health.py). Document request/response schemas in code docstrings.

#### Health & Status

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root redirect |
| `GET` | `/health` | Legacy health check |
| `GET` | `/api/health` | Legacy health check |
| `GET` | `/v1/health` | Standard health check |
| `GET` | `/v1/health/live` | Liveness probe |
| `GET` | `/v1/health/ready` | Readiness probe (checks JuniperData, CasCor) |

#### Training Control

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/train/start` | Start training |
| `POST` | `/api/train/pause` | Pause training |
| `POST` | `/api/train/resume` | Resume training |
| `POST` | `/api/train/stop` | Stop training |
| `POST` | `/api/train/reset` | Reset training state |
| `GET` | `/api/train/status` | Get training status |
| `POST` | `/api/set_params` | Apply training parameters |

#### Metrics & State

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/state` | Current training state |
| `GET` | `/api/status` | Training status |
| `GET` | `/api/metrics` | Current training metrics |
| `GET` | `/api/metrics/history` | Historical metrics |
| `GET` | `/api/network/stats` | Network statistics |

#### Network & Topology

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/topology` | Network topology |
| `GET` | `/api/topology/raw` | Raw topology data |
| `GET` | `/api/dataset` | Dataset information |
| `POST` | `/api/dataset/generate` | Generate dataset |
| `GET` | `/api/decision_boundary` | Decision boundary visualization |
| `GET` | `/api/statistics` | Network statistics |

#### Snapshots (HDF5)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/snapshots` | List snapshots |
| `GET` | `/api/v1/snapshots/history` | Snapshot history |
| `GET` | `/api/v1/snapshots/{id}` | Get specific snapshot |
| `POST` | `/api/v1/snapshots` | Create snapshot |
| `POST` | `/api/v1/snapshots/{id}/restore` | Restore snapshot |

#### Metrics Layouts

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/metrics/layouts` | List metric layouts |
| `GET` | `/api/v1/metrics/layouts/{name}` | Get layout |
| `POST` | `/api/v1/metrics/layouts` | Create layout |
| `DELETE` | `/api/v1/metrics/layouts/{name}` | Delete layout |

#### Infrastructure (Redis/Cassandra)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/redis/status` | Redis status |
| `GET` | `/api/v1/redis/metrics` | Redis metrics |
| `GET` | `/api/v1/cassandra/status` | Cassandra status |
| `GET` | `/api/v1/cassandra/metrics` | Cassandra metrics |
| `GET` | `/api/v1/workers/stats` | Worker statistics |
| `GET` | `/api/v1/workers/list` | Worker list |

#### Remote Workers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/remote/status` | Remote worker status |
| `POST` | `/api/remote/connect` | Connect to remote manager |
| `POST` | `/api/remote/start_workers` | Start workers |
| `POST` | `/api/remote/stop_workers` | Stop workers |
| `POST` | `/api/remote/disconnect` | Disconnect |

### WebSocket Channels

**Channels:**

| Path | Description |
|------|-------------|
| `/ws/training` | Stream metrics and state updates in real-time |
| `/ws/control` | Send commands (start, stop, pause, resume, reset) |
| `/ws` | Legacy WebSocket endpoint |

**Message Format:**

```python
{
    "type": "metrics" | "state" | "topology" | "event" | "control_ack",
    "timestamp": 1234567890.123,  # Unix timestamp in seconds
    "data": {...}  # Payload varies by type
}
```

**Threading Safety:**

```python
# From background thread -> async WebSocket
websocket_manager.broadcast_from_thread(message)

# From async context
await websocket_manager.broadcast(message)
```

**Backward Compatibility Rule:**

- Do not change existing payload keys without versioning
- Add new keys as optional
- Update dashboard consumers before changing contracts
- Add integration tests for all contract changes

---

## Code Style Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### File Headers

All Python files should include the standard project header:

```python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       <version>
# File Name:     <filename>.py
# File Path:     <Project>/<Sub-Project>/<Application>/<Source Directory Path>/
#
# Created Date:  <date created>
# Last Modified: <date last changed>
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     <High level description of the current script>
#
#####################################################################################################################################################################################################
# Notes:
#     <Additional information about the script>
#
#####################################################################################################################################################################################################
# References:
#     <External information sources or documentation relevant to the script>
#
#####################################################################################################################################################################################################
# TODO :
#     <List of pending tasks or improvements for the script>
#
#####################################################################################################################################################################################################
# COMPLETED:
#     <List of completed tasks or features for the script>
#
#####################################################################################################################################################################################################
```

### Naming Conventions

- **Classes:** PascalCase (e.g., `DemoMode`, `WebSocketManager`)
- **Functions/Methods:** snake_case (e.g., `get_metrics_history`, `broadcast_from_thread`)
- **Constants:** _UPPER_SNAKE_CASE (e.g., `_MAX_EPOCHS`, `_DEFAULT_PORT`)
- **Private attributes:** Prefix with double underscore (e.g., `self.__private_data`)
- **Protected attributes:** Prefix with single underscore (e.g., `self._lock`)

### Metric Naming Standard

- Use snake_case for all metric names
- Prefix with `train_` or `val_` where relevant (e.g., `train_loss`, `val_loss`, `train_accuracy`, `val_accuracy`)
- Standard metrics: `epoch`, `step`, `loss`, `accuracy`, `learning_rate`
- Follow consistent naming across backend and frontend for interoperability

### Blocking Rules

- **No global mutable state without locks** - All shared state must use `threading.Lock()` for protection
- **Any long-lived collections must be size-bounded** - Use `maxlen` for deques, limit history buffers to prevent memory leaks

### Thread Safety

When writing concurrent code:

```python
import threading

class ThreadSafeClass:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def update_state(self, value):
        """Thread-safe state update."""
        with self._lock:
            self.state = value

    def get_state(self):
        """Thread-safe state retrieval."""
        with self._lock:
            return self.state
```

### Async/Thread Communication

For calling async code from threads:

```python
import asyncio

# In async context (FastAPI startup)
event_loop = asyncio.get_running_loop()
websocket_manager.set_event_loop(event_loop)

# From background thread
websocket_manager.broadcast_from_thread(message)
```

### Error Handling

```python
def robust_function():
    """Handle errors appropriately."""
    try:
        # Main logic
        result = some_operation()
    except ImportError:
        # Expected errors - silent or debug logging
        logger.debug("Optional module not available")
    except SpecificException as e:
        # Known errors - warning logging
        logger.warning(f"Known issue: {type(e).__name__}: {e}")
        return default_value
    except Exception as e:
        # Unexpected errors - error logging
        logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        raise
```

---

## Further Reading

- [`AGENTS.md`](../AGENTS.md) — the resident agent guide this material was relocated from.
- [`docs/REFERENCE.md`](REFERENCE.md) — index of technical reference documents.
- [`docs/DOCUMENTATION_OVERVIEW.md`](DOCUMENTATION_OVERVIEW.md) — documentation navigation, and the
  authoring/maintenance rules relocated in the preceding cut.
