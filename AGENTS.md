# Juniper Canopy - Agent Development Guide

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
   - Check `src/constants.py` and `conf/app_config.yaml`
   - Respect the hierarchy: env vars (`CASCOR_*`) > YAML > constants

4. **Before changing WebSocket or API routes**
   - Update both FastAPI (`main.py`, `communication/websocket_manager.py`) and any Dash callbacks using those routes
   - Update `docs/api/` and tests in `src/tests/integration/`

5. **Before changing demo mode behavior**
   - Understand `src/demo_mode.py` and how `CASCOR_DEMO_MODE` controls app startup
   - Ensure `./demo` still starts successfully and tests still pass

6. **Singleton reset guidance**
   - If you add new singleton-like components, extend the `reset_singletons` fixture in `src/tests/conftest.py`

**Where to find more details:**

- [Constants Guide](docs/CONSTANTS_GUIDE.md)
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
| `requires_display` | Needs a GUI/display                       | Visualization / UI snapshot tests           |

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

> **Note:** `conftest.py` **forces** `CASCOR_DEMO_MODE=1` for the test process by default so tests do **not** require a real backend unless you explicitly enable it via `CASCOR_BACKEND_AVAILABLE=1`.

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

- **`client`** (module scope): FastAPI `TestClient` against `main.app` with `CASCOR_DEMO_MODE=1`. Use this for exercising API endpoints in tests without starting uvicorn.

- **`reset_singletons`** (function scope, autouse): Resets `ConfigManager`, `DemoMode`, and `CallbackContextAdapter` singletons before and after each test. **Agent guidance:** Do not bypass this fixture; if you introduce new singletons, extend this fixture to reset them.

- **`fake_backend_root`**: Creates a fake CasCor backend modules tree under a temporary directory. Use it to test `CascorIntegration` behavior without a real backend.

- **`ensure_test_data_directory`** (session scope, autouse): Ensures `src/tests/data/` exists and creates `sample_metrics.json` if missing.

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
flake8 src/ --max-line-length=120 --statistics
mypy src/ --ignore-missing-imports

# Auto-format code
black src/
isort src/

# Check for syntax errors
python -m py_compile src/**/*.py
```

### CI/CD

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
│   ├── app_config.yaml           # Main application config (see "Configuration Management")
│   ├── conda_environment.yaml    # Conda env spec for JuniperPython
│   ├── requirements.txt          # Pip dependencies
│   ├── Dockerfile                # Container image for Juniper Canopy
│   ├── docker-compose.yaml       # Local stack (app + services like Redis)
│   ├── logging_config.yaml       # Logging configuration
│   ├── init.conf                 # Shared shell init for utility scripts
│   └── ... (35+ shell/logging/env configs)
├── data/                         # Datasets for training/testing
├── docs/                         # Reference & subsystem documentation
│   ├── api/                      # API-level docs for FastAPI/Dash endpoints
│   ├── cascor/                   # CasCor backend integration docs
│   ├── cassandra/                # Persistence / Cassandra integration docs
│   ├── ci_cd/                    # CI/CD pipeline documentation
│   ├── demo/                     # Demo mode behavior & usage
│   ├── history/                  # Archived/superseded documentation
│   ├── phase0-3/                 # Historical design docs / early phases
│   ├── redis/                    # Redis/cache integration docs
│   ├── testing/                  # Testing guides and advanced scenarios
│   └── *.md                      # Quick start, environment setup, etc.
├── images/                       # Generated images/screenshots
├── logs/                         # Log files (runtime)
├── notes/                        # Development notes and implementation details
├── reports/                      # Test coverage and CI reports
├── src/                          # Source code
│   ├── backend/                  # CasCor backend integration & adapters
│   ├── communication/            # WebSocket management & protocol
│   ├── frontend/                 # Dash dashboard components & callbacks
│   │   └── components/           # Individual UI components
│   ├── logger/                   # Logging system
│   ├── tests/                    # Test suite
│   │   ├── unit/                 # Unit tests (fast, no external deps)
│   │   ├── integration/          # Integration tests (DB, files, backend)
│   │   ├── regression/           # Regression tests for fixed bugs
│   │   ├── performance/          # Performance/benchmark tests
│   │   ├── fixtures/             # Additional test fixtures
│   │   ├── mocks/                # Mock implementations
│   │   └── helpers/              # Test utility functions
│   ├── config_manager.py         # Configuration management
│   ├── constants.py              # Central constants (see "Constants Management")
│   ├── demo_mode.py              # Demo mode simulation
│   └── main.py                   # FastAPI + Dash application entrypoint
├── util/                         # Utility scripts (bash, invoked via ./demo, etc.)
├── demo                          # Root-level demo launcher script (bash)
├── conftest.py                   # Root pytest config (adds src/ to path)
├── pyproject.toml                # Python project config (black, isort, pytest, coverage)
└── AGENTS.md                     # This file
```

### Key Components

1. **FastAPI Backend** (`src/main.py`)
   - RESTful API endpoints
   - WebSocket endpoints for real-time communication
   - Integration with Dash dashboard

2. **Dash Dashboard** (`src/frontend/dashboard_manager.py`)
   - Interactive web UI
   - Real-time plotting
   - Network visualization

3. **Demo Mode** (`src/demo_mode.py`)
   - Simulated training for development
   - Thread-safe operation
   - Realistic metric generation

4. **WebSocket Manager** (`src/communication/websocket_manager.py`)
   - Connection management
   - Thread-safe broadcasting
   - Async/sync bridge

5. **Constants Module** (`src/constants.py`)
   - Centralized application constants
   - Type-safe configuration values
   - Training parameters, UI settings, server config

6. **CasCor Integration** (`src/backend/cascor_integration.py`) - P1-NEW-003, P1-NEW-002
   - Async training support via `ThreadPoolExecutor`
   - `fit_async()` and `start_training_background()` methods
   - RemoteWorkerClient integration for distributed training
   - Thread-safe training status tracking

## Demo Mode vs Real Backend

### Demo Mode (Default for Development)

- **Activation:** Set `CASCOR_DEMO_MODE=1` (the `./demo` script does this automatically)
- **Behavior:** Simulated training loop, no real CasCor backend required
- **Use case:** UI development, testing, demonstrations

```bash
# Run in demo mode
./demo
# or explicitly:
export CASCOR_DEMO_MODE=1
cd src && uvicorn main:app --host 0.0.0.0 --port 8050
```

### Real Backend Mode (Production)

- **Activation:** Unset `CASCOR_DEMO_MODE` and set `CASCOR_BACKEND_PATH`
- **Behavior:** Connects to real CasCor neural network backend
- **Use case:** Production, real training sessions

```bash
# Run with real backend
unset CASCOR_DEMO_MODE
export CASCOR_BACKEND_PATH=/path/to/cascor
cd src && uvicorn main:app --host 0.0.0.0 --port 8050
```

### Agent Guidance for Demo Mode

- **Tests must work with demo mode**: `conftest.py` forces `CASCOR_DEMO_MODE=1` by default
- **New features must be demo-aware**: Check `demo_mode_active` before calling real backend
- **Use `CascorIntegration` carefully**: Only behind checks that respect demo mode and `CASCOR_BACKEND_AVAILABLE`

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

All application constants are centralized in `src/constants.py` for maintainability and type safety.

**Import and use constants:**

```python
from constants import TrainingConstants, DashboardConstants

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

See the comprehensive [Constants Guide](docs/CONSTANTS_GUIDE.md) for detailed instructions on:

- How to add new constants
- Naming conventions (include units: `_MS`, `_S`, `_PX`)
- Constants vs configuration
- Best practices and examples

## Configuration Management

### Configuration Hierarchy

The juniper_canopy application uses a three-level configuration hierarchy (highest to lowest priority):

1. **Environment Variables** (CASCOR_*) - Runtime overrides
2. **YAML Configuration** (conf/app_config.yaml) - Deployment-specific settings
3. **Constants Module** (src/constants.py) - Application defaults

This hierarchy allows flexible deployment while maintaining sensible defaults.

### Environment Variable Overrides

All configuration values can be overridden via environment variables with the `CASCOR_` prefix.

#### Server Configuration

```bash
export CASCOR_SERVER_HOST=0.0.0.0          # Server bind address (default: 127.0.0.1)
export CASCOR_SERVER_PORT=8051             # Server port (default: 8050)
export CASCOR_SERVER_DEBUG=1               # Debug mode: 1/true/yes or 0/false/no
```

#### Training Parameters

```bash
export CASCOR_TRAINING_EPOCHS=300          # Maximum training epochs (default: 200)
export CASCOR_TRAINING_LEARNING_RATE=0.02  # Learning rate (default: 0.01)
export CASCOR_TRAINING_HIDDEN_UNITS=15     # Max hidden units (default: 10)
```

#### Frontend Components

```bash
# Metrics Panel
export JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS=500  # Update interval in ms (default: 1000)
export JUNIPER_CANOPY_METRICS_BUFFER_SIZE=5000        # Data buffer size (default: 10000)
export JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW=20     # Smoothing window (default: 10)
```

#### Backend Integration

```bash
export CASCOR_BACKEND_PATH=/custom/path/to/cascor  # CasCor backend path (default: ../cascor)
```

#### WebSocket Configuration

```bash
export CASCOR_WEBSOCKET_MAX_CONNECTIONS=100      # Max concurrent connections (default: 50)
export CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL=60    # Heartbeat interval in seconds (default: 30)
export CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS=10    # Reconnection attempts (default: 5)
export CASCOR_WEBSOCKET_RECONNECT_DELAY=5        # Delay between reconnects in seconds (default: 2)
```

#### Demo Mode

```bash
export CASCOR_DEMO_UPDATE_INTERVAL=0.5   # Simulation step interval in seconds (default: 1.0)
export CASCOR_DEMO_CASCADE_EVERY=40      # Add hidden unit every N epochs (default: 30)
```

### YAML Configuration

Configuration file location: `conf/app_config.yaml`

Example configuration structure:

```yaml
application:
  server:
    host: "127.0.0.1"
    port: 8050
    debug: false

training:
  parameters:
    epochs:
      min: 10
      max: 1000
      default: 200
      description: "Maximum training epochs"
      modifiable_during_training: false

    learning_rate:
      min: 0.0001
      max: 1.0
      default: 0.01
      description: "Learning rate for training"
      modifiable_during_training: true

frontend:
  training_metrics:
    enabled: true
    buffer_size: 5000
    update_frequency_hz: 10
    smoothing_window: 10

backend:
  cascor_integration:
    backend_path: "../cascor"

  communication:
    websocket:
      enabled: true
      max_connections: 50
      heartbeat_interval: 30
      reconnect_attempts: 5
      reconnect_delay: 2
```

### Using Configuration in Code

```python
import os
from config_manager import ConfigManager
from constants import ServerConstants

# Initialize ConfigManager
config_mgr = ConfigManager()

# Get configuration with proper fallback hierarchy
host_config = config_mgr.config.get('application', {}).get('server', {}).get('host')
host = os.getenv("CASCOR_SERVER_HOST") or host_config or ServerConstants.DEFAULT_HOST

# Log configuration source for transparency
host_source = "env" if os.getenv("CASCOR_SERVER_HOST") else ("config" if host_config else "constant")
logger.info(f"Using host={host} (source: {host_source})")
```

### Configuration Best Practices

1. **Always provide fallbacks**: Use the three-level hierarchy (env > config > constant)
2. **Validate user input**: Use `config_mgr.validate_training_param_value()` for user-provided values
3. **Log configuration sources**: Help users debug configuration issues
4. **Handle errors gracefully**: Invalid env vars should fall back to config/constant
5. **Document all overrides**: Comment why environment variables are being set

### Testing Configuration

```bash
# Run configuration tests
cd src
pytest tests/unit/test_config_refactoring.py -v          # Unit tests (35 tests)
pytest tests/integration/test_config_integration.py -v   # Integration tests (24 tests)

# Test with environment variable overrides
export CASCOR_TRAINING_EPOCHS=500
export CASCOR_SERVER_PORT=8051
./demo
# Verify dashboard shows epochs=500 and server starts on port 8051

# Validate configuration loading
python -c "from config_manager import ConfigManager; cm = ConfigManager(); print('Config valid')"
```

### Configuration Troubleshooting

**Problem**: Environment variable not taking effect

**Solution**: Check variable name exactly matches expected format (CASCOR_*)

```bash
# Correct
export CASCOR_TRAINING_EPOCHS=300

# Incorrect (missing CASCOR_ prefix)
export TRAINING_EPOCHS=300
```

**Problem**: Configuration value seems wrong

**Solution**: Check configuration source logging to see which level is being used

```bash
# Application logs show configuration sources
# Example: "Starting server on 127.0.0.1:8051 (host source: config, port source: env)"
```

**Problem**: YAML configuration not loading

**Solution**: Verify YAML syntax and file location

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"

# Check config path
python -c "from config_manager import ConfigManager; cm = ConfigManager(); print(cm.config_path)"
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

Configuration is managed via:

1. `conf/app_config.yaml` - Base configuration
2. Environment variables - Override config values
3. Environment variable format: `CASCOR_<SECTION>_<KEY>`

Example:

```bash
export CASCOR_SERVER_PORT=8051
export CASCOR_DEBUG=1
export CASCOR_DEMO_MODE=1
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
export CASCOR_DEBUG=1

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
# Set backend path
export CASCOR_BACKEND_PATH=/path/to/cascor

# Run application
cd src
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

### Docker (Future)

```bash
docker-compose up
```

## API and WebSocket Contracts

### REST API Endpoints

All REST endpoints defined in [src/main.py](src/main.py). Document request/response schemas in code docstrings.

**Key Endpoints:**

- `GET /api/metrics` - Current training metrics
- `GET /api/metrics/history` - Historical metrics
- `GET /api/network/topology` - Network structure
- `GET /api/decision_boundary` - Decision boundary data for visualization
- `GET /api/dataset` - Current dataset points

### WebSocket Channels

**Channels:**

- `/ws/training` - Stream metrics and state updates in real-time
- `/ws/control` - Send commands (start, stop, pause, resume, reset)

**Message Format:**

```python
{
    "type": "metrics" | "state" | "topology" | "event",
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

The demo mode must accurately simulate the real CasCor backend to enable UI development without backend dependency.

**Requirements:**

- Produce realistic training loop with pause/resume/reset capabilities
- Match CasCor backend payload shapes, keys, and update cadence
- Expose identical API/WebSocket interfaces (UI code must be agnostic)
- Support thread-safe control via Events (clean stop/pause)
- Started via `./demo` or `util/juniper_canopy-demo.bash` (conda activation required)

**Implementation:** [src/demo_mode.py](src/demo_mode.py)

**Non-MVP Features (see [DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md)):**

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

1. `conf/app_config.yaml` - Base configuration
2. Environment variable overrides: `CASCOR_<SECTION>_<KEY>`
3. Supports `${VAR}` and `$VAR` expansion

**Example:**

```bash
export CASCOR_SERVER_PORT=8051
export CASCOR_DEBUG=1
export CASCOR_DEMO_MODE=1
export CASCOR_BACKEND_PATH=/path/to/cascor  # Default: ../cascor
```

## File Placement Rules

Organize files according to their purpose:

| File Type     | Location                                    | Examples                            |
| ------------- | ------------------------------------------- | ----------------------------------- |
| Source code   | `src/` and logical subdirs                  | `src/demo_mode.py`, `src/frontend/` |
| Tests         | `src/tests/{unit,integration,performance}/` | `src/tests/unit/test_demo_mode.py`  |
| Documentation | `notes/`                                    | `notes/DEVELOPMENT_ROADMAP.md`      |
| Configuration | `conf/`                                     | `conf/app_config.yaml`              |
| Datasets      | `data/`                                     | `data/spiral_dataset.csv`           |
| Logs          | `logs/`                                     | `logs/system.log`                   |
| Images        | `images/`                                   | `images/network_topology.png`       |
| Scripts       | `util/`                                     | `util/juniper_canopy-demo.bash`     |

**Mirror package structure in tests:**

```bash
src/demo_mode.py           -> src/tests/unit/test_demo_mode.py
src/communication/         -> src/tests/unit/test_websocket_manager.py
```

## Documentation Organization

The project documentation follows a structured organization with clear separation between current and historical content:

### Root Directory Documentation

High-level documentation in the project root for quick access:

- **README.md** - Project overview, quick start, features
- **QUICK_START.md** - 5-minute setup guide (get running ASAP)
- **ENVIRONMENT_SETUP.md** - Complete environment configuration
- **CHANGELOG.md** - Chronological change history with impact analysis
- **AGENTS.md** - This file - comprehensive developer guide
- **DOCUMENTATION_OVERVIEW.md** - Navigation guide to all documentation

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

### docs/ Subdirectory

Technical deep-dive documentation:

- **docs/ci_cd/CICD_MANUAL.md** - CI/CD comprehensive usage guide
- **docs/ci_cd/CICD_QUICK_START.md** - CI/CD 5-minute setup
- **docs/ci_cd/CICD_REFERENCE.md** - CI/CD technical reference
- **docs/ARCHITECTURE.md** - System architecture (future)
- **docs/API_REFERENCE.md** - API documentation (future)
- **docs/DEPLOYMENT.md** - Deployment guide (future)

### docs/history/ Archive

Historical documentation with timestamp-based naming:

- **docs/history/INDEX.md** - Archive index with descriptions
- **docs/history/FILENAME_YYYY-MM-DD.ext** - Archived versions
- **docs/history/consolidated/** - Superseded consolidated docs

Examples:

- `docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md` - Superseded by split testing docs
- `docs/history/BACKEND_INTEGRATION_2025-11-04.md` - Obsolete integration docs

### notes/ Subdirectory

Development notes and technical details:

- **notes/DEVELOPMENT_ROADMAP.md** - Feature roadmap and status
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
5. **Update notes/DEVELOPMENT_ROADMAP.md** - Mark feature complete
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
5. **Update notes/DEVELOPMENT_ROADMAP.md** - Document migration path
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

3. **Update docs/history/INDEX.md:**

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
✓ Check [Archive Index](docs/history/INDEX.md) for older versions

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
✓ [Archive Index](docs/history/INDEX.md)

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

**Template:** [notes/TEMPLATE_SECURITY_RELEASE_NOTES.md](notes/TEMPLATE_SECURITY_RELEASE_NOTES.md)

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
- [ ] **notes/DEVELOPMENT_ROADMAP.md** - Mark feature complete, update status

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
- [ ] **notes/DEVELOPMENT_ROADMAP.md** - Document migration path

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

- [ ] **docs/history/INDEX.md** - Document archived files
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

Add entry to `docs/history/INDEX.md`:

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

`docs/history/INDEX.md` should maintain chronological organization:

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

3. **[notes/DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md)** - Update status
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
- [ ] [notes/DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md) status updated
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

## Recent Changes

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
   - Multi-version Python testing (3.11, 3.12, 3.13)
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
- [DEVELOPMENT_ROADMAP.md](notes/DEVELOPMENT_ROADMAP.md) - Updated roadmap

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
