# Juniper Canopy - Agent Development Guide

**Version**: 0.4.0

## Project Overview

The juniper_canopy prototype is a real-time monitoring and diagnostic frontend for the Cascade Correlation Neural Network (CasCor) prototype. It provides:

- Real-time network training visualization
- Interactive decision boundary plotting
- Network topology visualization with dynamic updates
- Training metrics and performance statistics
- Demo mode for development without backend connection
- Standardized WebSocket message protocol

## AI Agent Quick Start

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

### CI/CD

**GitHub Actions Workflows** (`.github/workflows/`):

| Workflow | File | Purpose |
|----------|------|---------|
| Continuous Integration | `ci.yml` | Test, lint, type-check on PR and push |
| Lockfile Update | `lockfile-update.yml` | Automated dependency lock updates |
| Publish | `publish.yml` | Release publishing automation |
| Security Scan | `security-scan.yml` | Security vulnerability scanning |

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
   - See [Configuration Management](#configuration-management) for details

3. **Dash Dashboard** (`src/frontend/dashboard_manager.py`)
   - `DashboardManager` orchestrates all UI components
   - 13 specialized panel components in `frontend/components/`
   - Interactive real-time plotting via Plotly/Dash callbacks

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

Containerization configs live under `conf/`:

- `conf/Dockerfile` – Builds a Juniper Canopy image (FastAPI + Dash + demo/backend integration)
- `conf/docker-compose.yaml` – Optional local stack (app + supporting services like Redis)

### Basic Docker Usage

```bash
# Build image
docker build -f conf/Dockerfile -t juniper_canopy .

# Run container
docker run --rm -p 8050:8050 juniper_canopy

# Or with docker-compose
docker compose -f conf/docker-compose.yaml up --build
```

### Agent Guidance for Docker

- Keep ports and environment variables consistent with `app_config.yaml` and `ServerConstants`
- If you change API paths or WebSocket endpoints, update both FastAPI routes and Docker/docker-compose health checks
- The canonical entrypoint is `uvicorn main:app`—if this changes, update `conf/Dockerfile`

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
- `ServerConstants` - Server configuration (host, port, WebSocket paths)

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

## Code Style Guidelines

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

## Environment Setup

### Conda Environment

The project uses the JuniperPython conda environment:

```bash
# Location
/opt/miniforge3/envs/JuniperPython

# Activate manually
conda activate JuniperPython

# Python interpreter path
/opt/miniforge3/envs/JuniperPython/bin/python
```

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
/opt/miniforge3/envs/JuniperPython/bin/python main.py

# Or activate environment first
conda activate JuniperPython
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
/opt/miniforge3/envs/JuniperPython/bin/python -u main.py
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
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

### Docker

```bash
# Build image (root Dockerfile)
docker build -t juniper-canopy .

# Run container
docker run --rm -p 8050:8050 juniper-canopy

# Or with docker-compose (conf/ directory)
docker compose -f conf/docker-compose.yaml up --build
```

## API and WebSocket Contracts

### REST API Endpoints

All REST endpoints defined in [src/main.py](src/main.py) and [src/health.py](src/health.py). Document request/response schemas in code docstrings.

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

## Demo Mode Contract

The demo mode must accurately simulate the real CasCor backend to enable UI development without backend dependency. Both `DemoBackend` and `ServiceBackend` implement the same `BackendProtocol` interface.

**Requirements:**

- Produce realistic training loop with pause/resume/reset capabilities
- Match CasCor backend payload shapes, keys, and update cadence
- Expose identical API/WebSocket interfaces via `BackendProtocol` (UI code must be agnostic)
- Support thread-safe control via Events (clean stop/pause)
- Started via `./demo` or `util/juniper_canopy-demo.bash` (conda activation required)

**Implementation:** [src/demo_mode.py](src/demo_mode.py)

**Non-MVP Features (see [DEVELOPMENT_ROADMAP.md](notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md)):**

- HDF5 snapshot playback
- Export formats (Cytoscape)
- Animated per-weight visualization

## Path and Environment Rules

### Conda Environment, Path and Environment

**Always use JuniperPython conda environment:**

```bash
# Location
/opt/miniforge3/envs/JuniperPython

# Python interpreter path
/opt/miniforge3/envs/JuniperPython/bin/python
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

| File Type     | Location                                    | Examples                            |
| ------------- | ------------------------------------------- | ----------------------------------- |
| Source code   | `src/` and logical subdirs                  | `src/demo_mode.py`, `src/frontend/` |
| Tests         | `src/tests/{unit,integration,performance}/` | `src/tests/unit/test_demo_mode.py`  |
| Documentation | `notes/`                                    | `notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md`      |
| Configuration | `conf/`                                     | `conf/app_config.yaml`              |
| Datasets      | `data/`                                     | `data/spiral_dataset.csv`           |
| Logs          | `logs/`                                     | `logs/system.log`                   |
| Images        | `images/`                                   | `images/network_topology.png`       |
| Scripts       | `util/`                                     | `util/juniper_canopy-demo.bash`     |

**Mirror package structure in tests:**

```bash
src/demo_mode.py           -> src/tests/unit/test_demo_mode_*.py
src/communication/         -> src/tests/unit/test_websocket_*.py
```

## Documentation Organization

The project documentation follows a structured organization with clear separation between current and historical content:

### Root Directory Documentation

High-level documentation in the project root for quick access:

- **README.md** - Project overview, quick start, features
- **CHANGELOG.md** - Chronological change history with impact analysis
- **AGENTS.md** - This file - comprehensive developer guide
- **CLAUDE.md** - Symlink to AGENTS.md (Claude Code integration)
- **LICENSE** - MIT License

### docs/ Directory Documentation

Reference and subsystem documentation:

- **docs/QUICK_START.md** - 5-minute setup guide (get running ASAP)
- **docs/ENVIRONMENT_SETUP.md** - Complete environment configuration
- **docs/DOCUMENTATION_OVERVIEW.md** - Navigation guide to all documentation
- **docs/DEVELOPER_CHEATSHEET.md** - Quick reference for developers
- **docs/REFERENCE.md** - Technical reference
- **docs/USER_MANUAL.md** - End-user documentation

### Integration-Specific Documentation

Integration guides with consistent naming pattern:

- **[INTEGRATION]_QUICK_START.md** - 5-minute integration setup
- **[INTEGRATION]_MANUAL.md** - Comprehensive usage guide
- **[INTEGRATION]_REFERENCE.md** - Technical API/configuration reference

Current integrations:

- **REDIS_*** - Redis integration documentation
- **CASSANDRA_*** - Cassandra integration documentation
- **CASCOR_BACKEND_*** - CasCor backend integration documentation

### Testing Documentation

Comprehensive testing documentation suite:

- **TESTING_QUICK_START.md** - Get testing in 5 minutes
- **TESTING_MANUAL.md** - Complete testing guide
- **TESTING_REFERENCE.md** - Technical testing reference
- **TESTING_ENVIRONMENT_SETUP.md** - Test environment configuration
- **TESTING_REPORTS_COVERAGE.md** - Coverage analysis and reports

### docs/ Subdirectories

Technical deep-dive documentation organized by topic:

- **docs/api/** - API schema and reference documentation
- **docs/cascor/** - CasCor backend integration (manual, quick start, reference, constants guide)
- **docs/cassandra/** - Cassandra integration documentation
- **docs/ci_cd/** - CI/CD pipeline documentation (manual, quick start, reference, environment setup)
- **docs/demo/** - Demo mode documentation (manual, quick start, reference, environment setup)
- **docs/deployment/** - Kubernetes deployment plan
- **docs/history/** - Archived/superseded documentation
- **docs/redis/** - Redis integration documentation
- **docs/testing/** - Testing guides, analysis reports, selective test enablement

### docs/history/ Archive

Historical documentation with timestamp-based naming:

- **docs/history/FILENAME_YYYY-MM-DD.ext** - Archived versions
- **notes/history/INDEX.md** - Archive index with descriptions

Examples:

- `docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md` - Superseded by split testing docs
- `docs/history/BACKEND_INTEGRATION_2025-11-04.md` - Obsolete integration docs

### notes/ Subdirectory

Development notes and technical details:

- **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Feature roadmap and status
- **notes/FINAL_STATUS_*.md** - Major milestone summaries
- **notes/IMPLEMENTATION_*.md** - Implementation details
- **notes/FIX_*.md** - Bug fix reports
- **notes/CI_CD_*.md** - CI/CD implementation notes

## Documentation Maintenance Workflow

### When to Update Documentation

Update documentation systematically based on the type of change:

#### On Feature Addition

1. **Update [INTEGRATION]_MANUAL.md** - Add feature usage instructions
2. **Update [INTEGRATION]_REFERENCE.md** - Add API/configuration details
3. **Update CHANGELOG.md** - Add entry under "Added" section
4. **Update README.md** - If feature changes core capabilities
5. **Update notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Mark feature complete
6. **Add to Recent Changes** - Link implementation notes in AGENTS.md

#### On Bug Fix

1. **Update CHANGELOG.md** - Add entry under "Fixed" section
2. **Update troubleshooting sections** - In relevant manuals
3. **Update notes/** - Create fix report (e.g., `FIX_[ISSUE]_[DATE].md`)
4. **Update TESTING_*.md** - If test coverage added
5. **Add to Recent Changes** - Link fix details in AGENTS.md

#### On Breaking Change

1. **Update CHANGELOG.md** - Prominent entry under "Changed" with migration guide
2. **Update QUICK_START.md** - Reflect new setup/usage
3. **Update all affected manuals** - Update instructions
4. **Update all affected references** - Update API/config docs
5. **Update notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Document migration path
6. **Create migration guide** - In docs/ if complex

#### On Test Addition

1. **Update TESTING_MANUAL.md** - Document new test types/approaches
2. **Update TESTING_REFERENCE.md** - Add test command variations
3. **Update TESTING_REPORTS_COVERAGE.md** - Update coverage metrics
4. **Update CHANGELOG.md** - If significant coverage improvement

#### On Deployment/Infrastructure Change

1. **Update docs/ci_cd/CICD_MANUAL.md** - Update pipeline documentation
2. **Update ENVIRONMENT_SETUP.md** - Update setup instructions
3. **Update DEPLOYMENT_GUIDE.md** - Update deployment steps (when created)
4. **Update CHANGELOG.md** - Document infrastructure changes

### Versioning and Archival Procedures

#### When to Archive Documentation

Archive documentation when:

1. **Major version changes** - Archive old version-specific docs
2. **Documentation consolidation** - Archive superseded individual files
3. **Documentation reorganization** - Archive old structure
4. **Documentation splits** - Archive consolidated docs when splitting

#### Archive Process

1. **Create timestamp-based filename:**

   ```bash
   FILENAME_YYYY-MM-DD.ext
   # Example: TESTING_GUIDE_CONSOLIDATED_2025-11-04.md
   ```

2. **Move to docs/history/:**

   ```bash
   mv FILENAME.md docs/history/FILENAME_YYYY-MM-DD.md
   ```

3. **Update notes/history/INDEX.md:**

   ```markdown
   ## YYYY-MM-DD: Archive Description

   - **[FILENAME](FILENAME_YYYY-MM-DD.md)** - Reason for archival, replacement docs
   ```

4. **Add redirect notice to new docs:**

   ```markdown
   > **Note:** This document replaces [Old Doc](docs/history/OLD_DOC_2025-11-04.md) archived on 2025-11-04.
   ```

5. **Update navigation links** - Ensure all cross-references point to current docs

#### Archive Examples

```bash
# Consolidation → split
docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md
# Replaced by: TESTING_QUICK_START.md, TESTING_MANUAL.md, TESTING_REFERENCE.md

# Superseded integration guide
docs/history/BACKEND_INTEGRATION_2025-11-04.md
# Replaced by: CASCOR_BACKEND_QUICK_START.md, CASCOR_BACKEND_MANUAL.md
```

### Cross-Referencing Requirements

Maintain consistent cross-references across documentation:

#### Internal Links

Use relative markdown links with descriptive text:

✓ See [Testing Quick Start](TESTING_QUICK_START.md) for setup
✓ Refer to [API Reference](docs/API_REFERENCE.md) for details
✓ Check [Archive Index](notes/history/INDEX.md) for older versions

✗ See docs/API_REFERENCE.md
✗ Click here: docs/testing.md

#### Code References

Link to specific files and line numbers:

✓ Implementation in [src/demo_mode.py](src/demo_mode.py)
✓ See [WebSocket Manager](src/communication/websocket_manager.py#L45-L67)
✓ Configuration in [conf/app_config.yaml](conf/app_config.yaml)

✗ See the demo mode file
✗ Check websocket manager

#### External Resources

Use descriptive link text with URLs:

✓ See [FastAPI Documentation](https://fastapi.tiangolo.com/)
✓ Refer to [WebSocket RFC 6455](https://tools.ietf.org/html/rfc6455)

✗ <https://fastapi.tiangolo.com/>
✗ See link: <https://example.com>

### Documentation Review Checklist

Before committing documentation changes:

- [ ] All internal links tested and working
- [ ] Code examples tested and accurate
- [ ] Version/last-updated stamps current
- [ ] Cross-references updated (if structure changed)
- [ ] Table of contents reflects all sections
- [ ] Markdown formatting validated
- [ ] No broken links to archived content
- [ ] CHANGELOG.md updated
- [ ] Archive INDEX.md updated (if archival)
- [ ] Navigation consistency maintained

## Documentation Standards

### Markdown Formatting Standards

#### Headers

- Use ATX-style headers (`#`, `##`, `###`)
- One H1 (`#`) per document (document title)
- Logical hierarchy without skipping levels
- Space after hash marks

✓ # Document Title
✓ ## Section
✓ ### Subsection

✗ #Document Title (no space)
✗ ## Section
    #### Subsection (skipped H3)

#### Code Blocks

- Use fenced code blocks with language specification
- Include comments for clarity
- Show both correct and incorrect examples where helpful

````bash
✓ ```python
  def example():
      """Proper code block."""
      pass
  ```

✓ ```bash
  # Show command with context
  pytest tests/ -v
  ```

✗ ```
  code without language
  ```
````

#### Lists

- Use `-` for unordered lists
- Use `1.` for ordered lists (auto-numbering)
- Indent nested lists with 3 spaces
- Blank line before/after lists

```bash
✓ - Item one
  - Nested item
  - Another nested
- Item two

✓ 1. First step
2. Second step
   - Sub-point
3. Third step

✗ * Mixed bullets
- Are confusing
```

#### Tables

- Use pipe tables with alignment
- Include header separator
- Align columns for readability

```bash
✓ | File Type     | Location                                    | Examples                            |
  | ------------- | ------------------------------------------- | ----------------------------------- |
  | Source    | `src/`   | `main.py` |

✗  |File|Loc|Ex|
|-|-|-|
|S-c|s-c|m-n|
||||
```

### Internal Linking Conventions

#### File Links

Use relative paths with descriptive link text:

✓ [Quick Start Guide](QUICK_START.md)
✓ [Testing Manual](TESTING_MANUAL.md)
✓ [CI/CD Manual](docs/ci_cd/CICD_MANUAL.md)
✓ [CI/CD Quick Start](docs/ci_cd/CICD_QUICK_START.md)
✓ [Archive Index](notes/history/INDEX.md)

✗ [Example Link](./docs/../TESTING_MANUAL.md)
✗ See TESTING_MANUAL.md

#### Section Links

Link to specific sections with anchors:

```bash
✓ [Installation](#installation)
✓ [Testing Guidelines](#testing-guidelines)
✓ [API Endpoints](#rest-api-endpoints)
# Anchors are auto-generated from headers:
```

##### Section Links: Examples

```markdown
## Testing Guidelines → #testing-guidelines

## REST API Endpoints → #rest-api-endpoints
```

#### Code File Links

Link to source code with file references:

```bash
✓ [main.py](src/main.py)
✓ [demo_mode.py](src/demo_mode.py)
✓ [WebSocket Manager](src/communication/websocket_manager.py)

# With line numbers (if viewer supports):
✓ [WebSocket broadcast](src/communication/websocket_manager.py#L45-L67)
```

### Code Example Formatting

#### Command Examples

Show commands with context and expected output:

```bash
# Run all tests with coverage
cd src
pytest tests/ --cov=. --cov-report=html

# Expected output:
# ===== 170 passed in 12.34s =====
# Coverage HTML report: ../reports/coverage/index.html
```

#### Python Examples

Include docstrings and type hints:

```python
def thread_safe_update(self, value: Any) -> None:
    """Thread-safe state update.

    Args:
        value: New state value
    """
    with self._lock:
        self.state = value
```

#### Configuration Examples

Show complete, working configurations:

```yaml
# conf/app_config.yaml
server:
  host: "127.0.0.1"
  port: 8050
  debug: false
```

### Tables of Contents Requirements

All manuals and reference docs must include a table of contents:

#### Document Table of Contents

- [Installation](#installation link)
- [Configuration](#configuration link)
- [Usage](#usage link)
  - [Basic Usage](#basic usage link)
  - [Advanced Usage](#advanced usage link)
- [Troubleshooting](#troubleshooting link)
- [Reference](#reference link)

**TOC Requirements:**

- Place after document metadata (version, date)
- Include all H2 headers at minimum
- Include H3 headers for complex sections
- Use consistent anchor formatting
- Update when structure changes

##### [Feature] Installation Link

Include Link to Installation Section of the Document

##### [Feature] Configuration Link

Include Link to Configuration Section of the Document

##### [Feature] Usage Link

Include Link to Usage Section of the Document

###### [Feature] Basic Usage Link

Include Link to Basic Usage Section of the Document

###### [Feature] Advanced Usage Link

Include Link to Advanced Usage Section of the Document

##### [Feature] Troubleshooting Link

Include Link to Troubleshooting Section of the Document

##### [Feature] Reference Link

Include Link to Reference Section of the Document

### Document Metadata

All documentation should include metadata:

#### Document Title Status, Version, and Last-Updated Stamps

**Last Updated:** 2025-11-05  
**Version:** 1.0.0  
**Status:** Current | Archived | Draft

**Update rules:**

- `Last Updated`: Date of last significant change
- `Version`: Semantic versioning (major.minor.patch)
- `Status`: Current (active), Archived (historical), Draft (in progress)

**Version incrementing:**

- **Major** (1.0.0 → 2.0.0): Breaking changes, complete rewrites
- **Minor** (1.0.0 → 1.1.0): New sections, significant additions
- **Patch** (1.0.0 → 1.0.1): Corrections, clarifications, minor updates

## Documentation File Types

### Quick Start Guides

**Purpose:** Get users running in 5 minutes or less

**Format:**

#### [Feature] Quick Start

**Last Updated:** YYYY-MM-DD
**Time to Complete:** ~5 minutes

##### Prerequisites

- Minimal requirements only

##### Installation

1. Step one
2. Step two
3. Step three

##### Verify Installation

```bash
# Quick verification command
```

##### Next Steps

- [Full Manual](FEATURE_MANUAL.md)
- [Reference](FEATURE_REFERENCE.md)

**Characteristics:**

- Ultra-concise (< 200 lines)
- Numbered steps only
- No theory or background
- Single "happy path" workflow
- Links to comprehensive docs

**Examples:** QUICK_START.md, TESTING_QUICK_START.md, REDIS_QUICK_START.md

### Environment Setup Guides

**Purpose:** Complete environment configuration from scratch

**Format:**

#### [Feature] Environment Setup

**Last Updated:** YYYY-MM-DD

##### Table of Contents, Environment Setup

- [System Requirements](#system-requirements: environment setup)
- [Conda Environment](#conda-environment: environment setup)
- [Dependencies](#dependencies: environment setup)
- [Configuration](#configuration: environment setup)
- [Verification](#verification: environment setup)
- [Troubleshooting](#troubleshooting: environment setup)

##### System Requirements, Environment Setup

- Operating system
- Python version
- System dependencies

##### Conda Environment, Environment Setup

Step-by-step environment setup...

##### Dependencies, Environment Setup

Dependencies required for feature...

##### Configuration, Environment Setup

Environment variables, config files...

##### Verification, Environment Setup

How to verify setup is correct...

##### Troubleshooting, Environment Setup

Common issues and solutions...

**Characteristics:**

- Comprehensive and detailed
- Platform-specific instructions
- Configuration examples
- Troubleshooting section
- Verification procedures

**Examples:** ENVIRONMENT_SETUP.md, TESTING_ENVIRONMENT_SETUP.md

### User Manuals

**Purpose:** Comprehensive feature usage guide

**Format:**

#### [Feature] User Manual

**Last Updated:** YYYY-MM-DD
**Version:** X.Y.Z

##### Table of Contents, User Manual

- [Overview](#overview: user manual)
- [Getting Started](#getting-started: user manual)
- [Basic Usage](#basic-usage: user manual)
- [Advanced Usage](#advanced-usage: user manual)
- [Best Practices](#best-practices: user manual)
- [Troubleshooting](#troubleshooting: user manual)
- [Examples](#examples: user manual)
- [Reference](#reference: user manual)

##### Overview: User Manual

What the feature does, why use it...

##### Getting Started: User Manual

Prerequisites, quick setup...

##### Basic Usage: User Manual

Common workflows with examples...

##### Advanced Usage: User Manual

Complex scenarios, customization...

##### Best Practices: User Manual

Recommendations, patterns to follow...

##### Troubleshooting: User Manual

Common issues, solutions, debugging...

##### Examples: User Manual

Real-world usage examples...

##### Reference: User Manual

Links to technical reference...

**Characteristics:**

- Task-oriented organization
- Progressive complexity (basic → advanced)
- Extensive examples
- Best practices section
- Troubleshooting guide
- Reference links

**Examples:** TESTING_MANUAL.md, REDIS_MANUAL.md, CASSANDRA_MANUAL.md

### Reference Documentation

**Purpose:** Technical API, configuration, and command reference

**Format:**

#### [Feature] Reference

**Last Updated:** YYYY-MM-DD
**Version:** X.Y.Z

##### Table of Contents: Reference

- [API Reference](#api-reference: reference)
- [Configuration](#configuration: docs)
- [Commands](#commands: reference)
- [Error Codes](#error-codes: reference)

##### API Reference: Reference

###### Function/Class Name

**Signature:**

```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """Brief description of function purpose."""
```

**Parameters:**

- `param1` (Type): Description
- `param2` (Type): Description

**Returns:**

- ReturnType: Description

**Raises:**

- Exception: When it occurs

**Example:**

```python
result = function_name(value1, value2)
```

##### Configuration: Reference

###### config_key

- **Type:** string | integer | boolean
- **Default:** `default_value`
- **Description:** What it configures
- **Example:** `config_key: value`

**Characteristics:**

- Alphabetical organization
- Complete parameter lists
- Type specifications
- Default values
- Example usage for each item
- Error code catalog

**Examples:** TESTING_REFERENCE.md, REDIS_REFERENCE.md, CASSANDRA_REFERENCE.md

### Integration Guides

**Purpose:** Third-party service integration documentation

**Naming Pattern:**

- `[SERVICE]_QUICK_START.md` - 5-minute setup
- `[SERVICE]_MANUAL.md` - Comprehensive guide
- `[SERVICE]_REFERENCE.md` - Technical reference

**Format:** Follows Quick Start, Manual, and Reference patterns above

**Additional Sections:**

- **Architecture**: How integration works
- **Configuration**: Service-specific settings
- **Authentication**: Credentials, security
- **Data Flow**: Request/response patterns
- **Monitoring**: Health checks, metrics
- **Troubleshooting**: Service-specific issues

**Examples:**

- Redis: REDIS_QUICK_START.md, REDIS_MANUAL.md, REDIS_REFERENCE.md
- Cassandra: CASSANDRA_QUICK_START.md, CASSANDRA_MANUAL.md, CASSANDRA_REFERENCE.md
- CasCor Backend: CASCOR_BACKEND_QUICK_START.md, CASCOR_BACKEND_MANUAL.md, CASCOR_BACKEND_REFERENCE.md

### Security Release Notes

**Purpose:** Document security patch releases addressing vulnerabilities in dependencies or application code.

**Template:** [notes/templates/TEMPLATE_SECURITY_RELEASE_NOTES.md](notes/templates/TEMPLATE_SECURITY_RELEASE_NOTES.md)

**Required Structure:**

1. **Title**: `JuniperCanopy v<VERSION> – SECURITY PATCH RELEASE`
2. **Summary paragraph**: Brief description of vulnerability and upgrade recommendation
3. **Security Impact table**: Vulnerable package, vulnerability class, attack vector, upstream fix
4. **Detailed vulnerability description**: How the vulnerability works and affects JuniperCanopy
5. **Affected Versions section**: Which versions are vulnerable and under what conditions
6. **Remediation / Upgrade Instructions**: Step-by-step upgrade guide with Git and pip commands
7. **Temporary Mitigation**: Workarounds if immediate upgrade is not possible
8. **Changes section**: List of security and documentation changes
9. **Testing & Quality table**: Test pass/skip counts, runtime, coverage
10. **Upgrade Recommendation**: Risk-specific guidance
11. **References**: Links to Dependabot alert, CVE/CWE, previous release notes, CHANGELOG

**Naming Convention:** `RELEASE_NOTES_v<VERSION>.md`

**Examples:**

- [RELEASE_NOTES_v0.14.1-alpha.md](notes/RELEASE_NOTES_v0.14.1-alpha.md) - filelock TOCTOU vulnerability
- [RELEASE_NOTES_v0.15.1-alpha.md](notes/RELEASE_NOTES_v0.15.1-alpha.md) - urllib3 decompression bomb vulnerability

## Update Triggers

Clear rules for when to update each documentation type:

### On Feature Addition, Update Docs

**Must Update:**

- [ ] **[FEATURE]_MANUAL.md** - Add usage instructions in relevant section
- [ ] **[FEATURE]_REFERENCE.md** - Add API/configuration documentation
- [ ] **CHANGELOG.md** - Add entry under `## [Unreleased] ### Added`
- [ ] **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Mark feature complete, update status

**May Update:**

- [ ] **README.md** - If feature changes core project capabilities
- [ ] **QUICK_START.md** - If feature affects initial setup
- [ ] **AGENTS.md Recent Changes** - Link to implementation notes

**Create:**

- [ ] **notes/IMPLEMENTATION_[FEATURE]_[DATE].md** - Implementation details

### On Bug Fix, Update Docs

**Must Update:**

- [ ] **CHANGELOG.md** - Add entry under `## [Unreleased] ### Fixed`
- [ ] **Troubleshooting sections** - In affected manuals

**May Update:**

- [ ] **TESTING_MANUAL.md** - If regression tests added
- [ ] **TESTING_REPORTS_COVERAGE.md** - If coverage changed
- [ ] **AGENTS.md Recent Changes** - Link to fix report

**Create:**

- [ ] **notes/FIX_[ISSUE]_[DATE].md** - Bug fix details and analysis

### On Breaking Change, Update Docs

**Must Update:**

- [ ] **CHANGELOG.md** - Prominent entry under `## [Unreleased] ### Changed` with migration guide
- [ ] **All affected QUICK_START.md files** - Update setup instructions
- [ ] **All affected MANUAL.md files** - Update usage instructions
- [ ] **All affected REFERENCE.md files** - Update API/config documentation
- [ ] **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Document migration path

**Create:**

- [ ] **docs/MIGRATION_[VERSION].md** - Migration guide (if complex)
- [ ] **notes/BREAKING_CHANGE_[FEATURE]_[DATE].md** - Impact analysis

### On Test Addition, Update Docs

**Must Update:**

- [ ] **TESTING_MANUAL.md** - Document new test types/approaches
- [ ] **TESTING_REFERENCE.md** - Add test command variations
- [ ] **TESTING_REPORTS_COVERAGE.md** - Update coverage metrics

**May Update:**

- [ ] **CHANGELOG.md** - If significant coverage improvement
- [ ] **README.md** - If testing approach changed

### On Deployment/Infrastructure Change, Update Docs

**Must Update:**

- [ ] **docs/ci_cd/CICD_MANUAL.md** - Update pipeline documentation
- [ ] **ENVIRONMENT_SETUP.md** - Update setup instructions
- [ ] **CHANGELOG.md** - Document infrastructure changes

**May Update:**

- [ ] **QUICK_START.md** - If deployment process changed
- [ ] **README.md** - If deployment approach changed

**Create:**

- [ ] **docs/DEPLOYMENT_GUIDE.md** - If not exists
- [ ] **notes/CI_CD_[CHANGE]_[DATE].md** - CI/CD change details

### On Documentation Reorganization, Update Docs

**Must Update:**

- [ ] **notes/history/INDEX.md** - Document archived files
- [ ] **DOCUMENTATION_OVERVIEW.md** - Update navigation
- [ ] **All internal cross-references** - Point to new locations
- [ ] **CHANGELOG.md** - Document reorganization under `Changed`

**Create:**

- [ ] **Archive files** - Move old docs to `docs/history/FILENAME_YYYY-MM-DD.ext`
- [ ] **Redirect notices** - In new docs pointing to archived versions

## Archive Procedures

### When to Archive

Archive documentation in these scenarios:

#### 1. Major Version Changes

When project reaches new major version (e.g., 1.x → 2.x):

```bash
# Archive version-specific docs
mv API_REFERENCE.md docs/history/API_REFERENCE_v1_2025-11-05.md
mv DEPLOYMENT_GUIDE.md docs/history/DEPLOYMENT_GUIDE_v1_2025-11-05.md
```

#### 2. Documentation Consolidation

When merging multiple docs into one:

```bash
# Before consolidation - multiple files
REDIS_SETUP.md
REDIS_USAGE.md
REDIS_API.md

# Archive old files
mv REDIS_SETUP.md docs/history/REDIS_SETUP_2025-11-05.md
mv REDIS_USAGE.md docs/history/REDIS_USAGE_2025-11-05.md
mv REDIS_API.md docs/history/REDIS_API_2025-11-05.md

# Create consolidated
REDIS_MANUAL.md  # Contains all content
```

#### 3. Documentation Splits

When splitting one doc into multiple (inverse of consolidation):

```bash
# Before split - single file
TESTING_GUIDE_CONSOLIDATED.md

# Archive consolidated version
mv TESTING_GUIDE_CONSOLIDATED.md docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md

# Create split files
TESTING_QUICK_START.md
TESTING_MANUAL.md
TESTING_REFERENCE.md
TESTING_ENVIRONMENT_SETUP.md
TESTING_REPORTS_COVERAGE.md
```

#### 4. Obsolete Documentation

When docs no longer apply to current system:

```bash
# Archive obsolete integration guide
mv BACKEND_INTEGRATION.md docs/history/BACKEND_INTEGRATION_2025-11-04.md

# Replaced by specific integration docs
CASCOR_BACKEND_MANUAL.md
```

### Archive Timestamp Format

Use ISO 8601 date format (YYYY-MM-DD):

```bash
# Correct formats
FILENAME_2025-11-04.md
FILENAME_v1.2_2025-11-04.md
FILENAME_CONSOLIDATED_2025-11-04.md

# Incorrect formats (don't use)
FILENAME_11-04-2025.md      # Wrong date order
FILENAME_2025-Nov-04.md     # Month abbreviation
FILENAME_20251104.md        # No separators
FILENAME_old.md             # No date
```

### Archive Process Steps

**1. Create Timestamped Filename:**

```bash
# Format: BASENAME_YYYY-MM-DD.ext
ORIGINAL="TESTING_GUIDE_CONSOLIDATED.md"
DATE=$(date +%Y-%m-%d)
ARCHIVED="TESTING_GUIDE_CONSOLIDATED_${DATE}.md"
```

**2. Move to Archive:**

```bash
# Ensure docs/history/ exists
mkdir -p docs/history/

# Move file
mv "$ORIGINAL" "docs/history/$ARCHIVED"
```

**3. Update Archive Index:**

Add entry to `notes/history/INDEX.md`:

## 2025-11-04: Testing Documentation Split

**Archived Files:**

- **[TESTING_GUIDE_CONSOLIDATED_2025-11-04.md](TESTING_GUIDE_CONSOLIDATED_2025-11-04.md)**
  - Reason: Split into focused documents for better navigation
  - Replaced by:
    - [TESTING_QUICK_START.md](../TESTING_QUICK_START.md) - 5-minute setup
    - [TESTING_MANUAL.md](../TESTING_MANUAL.md) - Comprehensive guide
    - [TESTING_REFERENCE.md](../TESTING_REFERENCE.md) - Technical reference
    - [TESTING_ENVIRONMENT_SETUP.md](../TESTING_ENVIRONMENT_SETUP.md) - Environment config
    - [TESTING_REPORTS_COVERAGE.md](../TESTING_REPORTS_COVERAGE.md) - Coverage reports
  - Content: Comprehensive testing guide with all sections consolidated

**4. Add Redirect Notice:**

In replacement documentation, add note at top:

```markdown
# Testing Quick Start
```

**Last Updated:** 2025-11-04
**Version:** 1.0.0

> **Note:** This document is part of the split testing documentation, replacing the consolidated guide
> [Testing Guide](docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md) archived on 2025-11-04.

**5. Update Cross-References:**

Search and update all links to archived docs:

```bash
# Find all references to archived doc
grep -r "TESTING_GUIDE_CONSOLIDATED.md" .

# Update links to point to new docs
# TESTING_GUIDE_CONSOLIDATED.md → TESTING_MANUAL.md (or appropriate replacement)
```

**6. Update CHANGELOG.md:**

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
```

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

## Documentation Update Workflow

**On every change, update these files:**

1. **[CHANGELOG.md](CHANGELOG.md)** - Summarize changes and impact
   - What changed
   - Why it changed
   - Impact on users/developers

2. **[README.md](README.md)** - Update if run/test instructions change
   - Installation steps
   - Quick start commands
   - Current features

3. **[notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md)** - Update status
   - Mark completed items
   - Update in-progress status
   - Add newly identified work

**Link relevant technical notes from "Recent Changes" section below.**

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
- [ ] [notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md) status updated
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

- [Main Juniper Documentation](../../../docs/)
- [CasCor Prototype](../../cascor/)
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

### 2026-02-05: Integration Development Plan - Comprehensive Assessment Complete

**Scope**: Evaluated 4 planning documents + rigorous source code review across JuniperCascor, JuniperCanopy, and JuniperData to consolidate all outstanding integration work.

**Source Documents Evaluated**:

- `JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN.md` (Phases 0-4 Complete, Phase 5 Deferred)
- `INTEGRATION_ROADMAP.md` (Most issues RESOLVED)
- `PRE-DEPLOYMENT_ROADMAP.md` (P0-P1 RESOLVED, some P2-P3 remaining)
- `PRE-DEPLOYMENT_ROADMAP-2.md` (74% complete, 26% remaining)

**Key Findings**:

- **3 CRITICAL code issues**: Real backend control not implemented (`main.py:433-442`), decision boundary incomplete for real backend (`main.py:779-788`), `get_network_data()` method missing from CascorIntegration (`main.py:627`)
- **3 HIGH issues**: `save_snapshot()`/`load_snapshot()` missing, async/sync boundary untested, no tests exercise real backend paths
- **8 MEDIUM issues**: Coverage gaps, type errors, remote workers untested, Cassandra/Redis integration gaps, monitoring race conditions, legacy code cleanup
- **30+ enhancement items**: CAN-001 through CAN-021 (Canopy), CAS-001 through CAS-010 (Cascor)

**Deliverable**: [notes/INTEGRATION_DEVELOPMENT_PLAN.md](notes/INTEGRATION_DEVELOPMENT_PLAN.md) - 53+ items organized into 4 prioritized phases

---

### 2026-02-04: Non-Passing Test Analysis and Remediation - Complete (Rounds 1 & 2)

**Round 1:** Analyzed and fixed 67 non-passing tests (54 ERROR, 10 FAILED, 3 XFAIL). Result: 3,207 passed.

**Round 1 Fixes:**

- **P0**: Installed `pytest-mock>=3.12` (resolved 54 ERROR tests in dashboard handler tests)
- **P1**: `main.py` - Added `not key.startswith("_")` filter in HDF5 snapshot creation (data integrity fix)
- **P2**: `test_main_coverage_extended.py` - Fixed race condition by draining broadcast messages before asserting control response
- **P3**: No change needed - 8 server-dependent tests correctly skip when `RUN_SERVER_TESTS` not set
- **P4**: `logger/logger.py` - Changed `logging.VERBOSE` to `self.VERBOSE_LEVEL` in `verbose()` method (Epic 3.6 CQ-001)
- **P5**: `logger/logger.py` - Added null check for empty YAML files in `LoggingConfig._load_config()` (Epic 3.6 CQ-001)

**Round 2:** Fixed additional test failures (5 skipping, 2 failing, 1 skipped, 1 race condition).

**Round 2 Fixes:**

- `main.py` - Added state message on `/ws/training` connect using `training_state.get_state()` format
- `test_websocket_state.py` - Rewrote 7 tests to consume deterministic connect sequence; removed `requires_server` marker
- `test_main_coverage.py`, `test_main_ws.py` - Updated ping-pong tests to drain 3rd connect message
- `test_logger_coverage.py` - Removed skip marker from `test_verbose_logging`
- `test_main_coverage_extended.py` - Fixed `test_unknown_command_returns_error` race condition
- `conftest.py` - Extended `reset_singletons` to reset `demo_mode._demo_instance` singleton

**Final result: 3,215 passed, 0 failed, 0 errors, 0 xfail, 37 skipped (all legitimate):**

**See:** [notes/FIX_FAILING_TESTS.md](notes/FIX_FAILING_TESTS.md)

---

### 2026-02-04: Test Suite & CI/CD Enhancement - Phase 2 Complete

**Conftest Consolidation (Epic 2.1):**

- Deleted duplicate `src/tests/fixtures/conftest.py`
- Single conftest.py now serves as source of truth for all fixtures

**Type Annotation Fixes (Epic 2.2):**

- Fixed ConfigManager `__init__` type annotation to accept Path objects

**Test Linting Enabled (Epic 2.3):**

- Added separate flake8 hook for tests with relaxed configuration
- Tests now linted with appropriate allowances (assert, random, higher complexity)

---

### 2026-02-04: Test Suite & CI/CD Enhancement - Phase 1 Complete

**Test Quality Improvements (Epic 1.1):**

Eliminated all false-positive tests that used `assert True` patterns:

- **test_button_responsiveness.py**: 4 tests now verify actual button behavior
- **test_button_state.py**: 1 test now verifies actual state changes
- **test_metrics_panel_coverage.py**: 1 test now verifies None handling
- **test_dashboard_manager.py**: Fixed exception handling test pattern
- **test_config_refactoring.py**: Converted to pytest.raises pattern
- **test_candidate_visibility.py**: Converted from manual script to proper pytest

**Test Organization Improvements (Epic 1.2):**

Moved 5 non-test files from test directory to `util/verification/`:

- `verify_yaml.py` - YAML configuration verification
- `verify_dashboard_init.py` - Dashboard initialization verification
- `verify_button_layout.py` - Button layout verification
- `implementation_script.py` - Implementation test script
- `verify_config_integration.py` - Config integration verification

**CI/CD Security Improvements (Epic 1.3):**

- Fixed Bandit security scan to properly fail on issues (removed `|| true`)
- Fixed pip-audit to fail on vulnerabilities (changed from warning to error)
- Added `.bandit.yml` configuration for security scan settings

**See:** [TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md](notes/TEST_SUITE_CICD_ENHANCEMENT_DEVELOPMENT_PLAN.md)

---

### 2026-02-01: CI/CD Parity Across All Juniper Applications

**Complete CI/CD Standardization:**

All three Juniper applications (JuniperCascor, JuniperData, JuniperCanopy) now use identical CI/CD settings:

- **Line Length**: 512 for all linters (black, isort, flake8)
- **Coverage Threshold**: 80% fail-under, 90% target
- **Build Stage**: Added to PR CI for all applications
- **yamllint**: Added to pre-commit for all applications
- **mypy**: Fully enabled in CI for all applications
- **Artifact Paths**: Standardized to reports/junit/, reports/htmlcov/, reports/coverage.xml
- **Python Matrix**: 3.12, 3.13, 3.14

**Files Updated:**

- `.pre-commit-config.yaml` (v1.2.0)
- `.github/workflows/ci.yml` (v0.12.0)
- `pyproject.toml` (v0.2.3)

**See:** `JuniperCascor/juniper_cascor/notes/JUNIPER_CASCOR_SPIRAL_DATA_GEN_REFACTOR_PLAN.md#15-cicd-parity-status` (external repo — see [pcalnon/juniper-cascor](https://github.com/pcalnon/juniper-cascor))

---

### 2025-11-11: CI/CD Documentation Consolidation

**Complete Reorganization:**

- **Consolidated:** 12 CI/CD files → 4 focused documents in docs/ci_cd/
- **New structure:**
  - CICD_QUICK_START.md - 5-minute setup
  - CICD_ENVIRONMENT_SETUP.md - Complete environment config
  - CICD_MANUAL.md - Comprehensive usage guide
  - CICD_REFERENCE.md - Technical reference
- **Archived:** 8 legacy files to docs/history/ (2025-11-11)
- **Result:** Cleaner navigation, reduced redundancy, single CI/CD location

**See:** [docs/ci_cd/CONSOLIDATION_SUMMARY.md](docs/ci_cd/CONSOLIDATION_SUMMARY.md)

---

### 2025-11-03: Complete Testing Infrastructure & CI/CD Implementation

**Massive Testing Overhaul:**

1. **Test Infrastructure Fixed (Task 1-2)**
   - Created `src/tests/conftest.py` at root for fixture discovery
   - Added singleton reset fixture for test isolation
   - Fixed pytest configuration
   - Eliminated all 21 fixture discovery errors
   - Result: 100% test pass rate

2. **WebSocket Implementation Fixed (Task 3)**
   - Added connection confirmation to `/ws/control` endpoint
   - Fixed demo mode initialization in test context
   - Resolved epoch reset race condition
   - Fixed command response handling
   - Result: All 10 WebSocket tests passing

3. **Frontend Testing Added (Task 4)**
   - Created 73 new frontend component tests
   - test_metrics_panel.py: 34 tests, 94% coverage
   - test_network_visualizer.py: 26 tests, 81% coverage
   - test_decision_boundary.py: 31 tests, 71% coverage
   - test_dataset_plotter.py: 25 tests, 82% coverage
   - test_dashboard_manager.py: 38 tests, 84% coverage
   - Result: Frontend coverage 71-94% (up from 22-45%)

4. **Complete CI/CD Pipeline (Task 5)**
   - GitHub Actions workflow with 6-stage pipeline
   - Multi-version Python testing (3.12, 3.13, 3.14)
   - Pre-commit hooks (Black, isort, Flake8, MyPy, Bandit)
   - Codecov integration
   - Quality gates (60% min coverage, 100% pass rate)
   - Result: Production-ready automation

**Metrics:**

- Test Errors: 21 → 0 (100% elimination)
- Test Failures: 17 → 0 (100% resolution)
- Tests Passing: 66 → 170+ (158% increase)
- Coverage: 5% → 73% (1,360% increase)
- Pass Rate: 58% → 100% (perfect)

**Documentation Created:** 15+ files, 10,000+ lines

**See:**

- [notes/FINAL_STATUS_2025-11-03.md](notes/FINAL_STATUS_2025-11-03.md) - Complete status
- [notes/TEST_FIXES_2025-11-03.md](notes/TEST_FIXES_2025-11-03.md) - Test fixes
- [notes/CI_CD_IMPLEMENTATION_2025-11-03.md](notes/CI_CD_IMPLEMENTATION_2025-11-03.md) - CI/CD details
- [docs/ci_cd/CICD_MANUAL.md](docs/ci_cd/CICD_MANUAL.md) - CI/CD complete guide
- [docs/ci_cd/CONSOLIDATION_SUMMARY.md](docs/ci_cd/CONSOLIDATION_SUMMARY.md) - CI/CD docs consolidated (2025-11-11)

### 2025-10-30: Pre-Deployment MVP Enhancements - Phase 2 Complete

**All P1 Priority Items Implemented:**

1. **Client-Side WebSocket (P1B)**
   - Created `src/frontend/assets/websocket_client.js` for real-time push updates
   - Dual WebSocket channels: `/ws/training` and `/ws/control`
   - Automatic reconnection with exponential backoff
   - <100ms latency for metrics updates
   - Replaces HTTP polling with efficient push architecture

2. **Training Controls (P1C)**
   - Added pause/resume/reset methods to DemoMode
   - Enhanced `/ws/control` endpoint for command handling
   - Thread-safe control flow with Events
   - Commands: start, stop, pause, resume, reset
   - Real-time status broadcasting to clients

3. **Comprehensive Testing (P1D)**
   - Created `test_demo_mode_advanced.py` (13 tests)
   - Created `test_config_manager_advanced.py` (12 tests)
   - Created `test_websocket_control.py` (10 tests)
   - 84% coverage for DemoMode (target 60%+ met)
   - Thread safety and integration tests

4. **Configuration Improvements (P1E)**
   - Environment variable expansion (${VAR}, $VAR)
   - Nested override collision handling
   - Configuration validation with defaults
   - Force reload support for tests
   - Enhanced error handling and logging

**Result:** ✅ MVP READY FOR DEPLOYMENT - All Phase 2 P1 items complete

**See:**

- [MVP_PRE_DEPLOYMENT_IMPLEMENTATION_2025-10-30.md](notes/MVP_PRE_DEPLOYMENT_IMPLEMENTATION_2025-10-30.md) - Complete implementation details
- [DEVELOPMENT_ROADMAP.md](notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md) - Updated roadmap

### 2025-10-29: Complete MVP Achievement

**Three Critical Fixes Applied:**

1. **Demo Script Python Interpreter** (Morning)
   - Fixed demo script to use conda environment Python
   - Added `exec "$CONDA_PREFIX/bin/python" -u main.py`
   - Resolves: `ModuleNotFoundError: No module named 'uvicorn'`

2. **Thread Safety & Architecture** (Morning)
   - Added locks and events to DemoMode
   - Implemented thread-safe WebSocket broadcasting
   - Standardized metric key naming (`val_loss`, `val_accuracy`)
   - Added bounded collections for memory management
   - Improved error handling and logging

3. **Dashboard Data Flow** (Afternoon)
   - Fixed API URL construction in dashboard callbacks
   - Added `_api_url()` helper using origin instead of host_url
   - Resolves: "No data available" in all dashboard tabs
   - All 4 tabs now display real-time data correctly

**Result:** ✅ MVP FULLY FUNCTIONAL - All tabs display data

**See:**

- [REGRESSION_FIX_REPORT.md](notes/REGRESSION_FIX_REPORT.md) - Thread safety fixes
- [MISSING_DATA_FIX_2025-10-29.md](notes/MISSING_DATA_FIX_2025-10-29.md) - Dashboard fix
- [COMPLETE_FIX_SUMMARY_2025-10-29.md](notes/COMPLETE_FIX_SUMMARY_2025-10-29.md) - All fixes
- [START_HERE.md](START_HERE.md) - Quick start guide

## WebSocket Message Schema

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
