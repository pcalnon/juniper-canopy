---
applyTo: '**'
---

# Copilot Instructions for the juniper_canopy prototype

The Juniper Canopy application servers as the CasCor NN Frontend

Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.
<!-- trunk-ignore-all(prettier) -->

## Project Overview

This is a prototype for developing a graphical frontend for Cascade Correlation (CasCor) neural networks. The project enables real-time monitoring of training progress, performance statistics, dataset visualization, decision boundaries, and graphical network representation.

Real-time monitoring frontend for Cascade Correlation neural networks. Monitors the CasCor prototype at `../../JuniperCascor/juniper_cascor` with FastAPI backend, Plotly Dash frontend, and WebSocket communication for live training visualization.

### Development Environment

- **OS**: Ubuntu Linux with conda environment management
- **IDE**: VS Code (primary development environment)
- **Language**: Python-based neural network backend with frontend TBD
- **Architecture**: Frontend-backend separation for neural network visualization

### Directory Structure & Conventions

Follow the strict project organization pattern established in `prompts/prompt_juniper_canopy.md`:

### Architecture Stack (Implemented)

- **Backend**: FastAPI with async/WebSocket support (`src/main.py`)
- **Frontend**: Plotly Dash for Python-native reactive UI (`src/frontend/dashboard_manager.py`)
- **Communication**: WebSocket bidirectional + SSE for metrics streaming (`src/communication/websocket_manager.py`)
- **Integration**: Direct hooks into CasCor training loop (`src/backend/cascor_integration.py`)
- **Config**: YAML-based with environment overrides (`conf/app_config.yaml`, `src/config_manager.py`)
- **Logging**: Dual-channel (console/file) with independent log levels (`src/logging/logger.py`)

### Critical Directory Structure

```bash
conf/              # YAML configs, requirements.txt, Docker/conda env files
data/{samples,testing,training}/  # Datasets with subdirectories
docs/              # Reference sources with URLs
images/            # Static generated images
logs/              # All log output (auto-created by logger)
notes/             # Design docs: architecture_design.md, technical_specifications.md, etc.
prompts/           # Original requirements and AI prompts
src/               # All source code
    backend/         # CasCor integration, training monitor, data adapter
    communication/   # WebSocket manager
    frontend/        # Dashboard manager, base component, components/
    logging/         # Multi-level logging framework
    tests/           # Unit/integration tests, mocks, helpers
util/             # Bash setup scripts (conda/mamba environment management)
```

## Essential Development Patterns

### 1. Configuration Access

```python
from config_manager import get_config
config = get_config()
value = config.get('section.key', default_value)  # Nested dot notation
```

Config supports environment variable overrides with `CASCOR_` prefix (e.g., `CASCOR_SERVER_PORT=8080`).

### 2. Logging Pattern (Independent Console/File Levels)

```python
from logging.logger import get_system_logger, get_training_logger, get_ui_logger
logger = get_system_logger()  # or get_training_logger(), get_ui_logger()
```

- Console/file log levels configured independently in `conf/app_config.yaml`
- Categories: `system`, `training`, `ui`, `communication`
- JSON format optional for structured logging
- Automatic rotation: midnight, 30-day retention, compression

### 3. CasCor Integration Hook Pattern

The integration uses method wrapping to inject monitoring without modifying CasCor source:

```python
# In src/backend/cascor_integration.py
cascor_integration.connect_to_cascor_network(network_instance)
cascor_integration.install_monitoring_hooks()  # Wraps train methods
```

### 4. Component Registration Pattern

```python
# Frontend components inherit from BaseComponent
class MyComponent(BaseComponent):
    def get_layout(self) -> html.Div: ...
    def register_callbacks(self, app): ...

# Register with dashboard
dashboard_manager.register_component(my_component)
```

## Environment & Workflow

### Conda Environment Requirement

**CRITICAL**: Before running ANY Python code or test, first activate:

```bash
conda activate JuniperCanopy
```

This provides torch, yaml, h5py, and all ML dependencies. The project was developed for Ubuntu but should work cross-platform.

### Setup Script Pattern

`util/setup_environment.bash` uses conditional conda/mamba detection:

```bash
USE_MAMBA="${TRUE}"  # or USE_MAMBA="${TRUE}"
# USE_CONDA="${TRUE}"  # or USE_MAMBA="${TRUE}"
CMD="${CONDA_CMD}"   # Automatically set based on flag
```

### Running the Application

```bash
# Simplistic launch
python ./src/main.py  # Starts FastAPI + Dash on localhost:8050

# Launch with environment configuration
./util/juniper_canopy.bash

# Convenience Script
./try
```

#### Running in Demo Mode

```bash
# Fully defined launch command
exec "/opt/miniforge3/envs/JuniperCanopy/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level debug

# Using Conda Environment Variable (export CONDA_PREFIX=/opt/miniforge3/envs/JuniperCanopy)
exec "$CONDA_PREFIX/bin/uvicorn" main:app --host 0.0.0.0 --port 8050 --log-level debug

# Using Launch Script
./util/juniper_canopy-demo.bash

# Using Convenience Script
./demo
```

### Development Server

```bash
## Key Files & Their Roles

```bash
| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app entry, WebSocket routes, startup/shutdown hooks |
| `src/config_manager.py` | Singleton config manager, YAML loading, env var substitution |
| `src/logging/logger.py` | `CascorLogger` class, colored console formatter, JSON file formatter |
| `src/backend/cascor_integration.py` | Method wrapping for CasCor network monitoring |
| `src/backend/training_monitor.py` | Metric collection, event callbacks |
| `src/backend/data_adapter.py` | Data format conversion between CasCor and frontend |
| `src/frontend/dashboard_manager.py` | Dash app initialization, layout, component lifecycle |
| `conf/app_config.yaml` | All settings: server, logging, frontend, backend paths |
```

## Path Configuration & Portability

### CasCor Backend Path

The config uses absolute paths for development. For portability across environments:

**Environment Variable (Recommended)**:

```bash
# Relative to frontend root
export CASCOR_BACKEND_PATH_REL="../../JuniperCascor/juniper_cascor"
# Or absolute for Ubuntu workstation:
export CASCOR_BACKEND_PATH_ABS="${HOME}/Development/python/JuniperCascor/juniper_cascor"
# Select one for now
export CASCOR_BACKEND_PATH="${CASCOR_BACKEND_PATH_ABS}"
```

**Config Override** (`conf/app_config.yaml`):

```yaml
backend:
    cascor_integration:
        backend_path: ${CASCOR_BACKEND_PATH:../../JuniperCascor/juniper_cascor}  # Env var with fallback
```

**Runtime Detection Pattern**:

```python
# In src/backend/cascor_integration.py
from pathlib import Path
import os

cascor_path = Path(os.getenv(
    'CASCOR_BACKEND_PATH',
    Path(__file__).parent.parent.parent.parent.parent / 'JuniperCascor/juniper_cascor'  # Relative fallback
))
```

**Primary development:**

- Platform: GPU Workstation
- OS Name: Ubuntu 25.10
- Dev Path: `/home/pcalnon/Development/...`

**Secondary development:**

- Platform: MacBook Pro, Intel, 2019
- OS Name: MacOS 13
- Dev Path: `/Users/pcalnon/Development/...`

## Common Pitfalls & Conventions

1. **Path Configuration**: Use `${CASCOR_BACKEND_PATH}` environment variable or relative paths (`../cascor`) for cross-environment compatibility.
2. **Import Pattern**: Components use relative imports within `src/`. Main.py adds `src/` to `sys.path`.
3. **Async Handlers**: WebSocket handlers in `main.py` use `async`/`await` - don't block the event loop.
4. **Dash Callbacks**: Must be registered in component's `register_callbacks()` method, called by DashboardManager.
5. **Log Directory**: Created automatically by logger if missing - don't manually create `logs/`.

## Redis Integration (Partial - Requires Completion)

Redis is configured but **partially implemented**. Complete implementation required:

### Current State

- Docker Compose includes Redis 7 Alpine container
- Config defines cache settings in `conf/app_config.yaml`:

```yaml
backend.cache:
    enabled: true
    type: redis
    redis_url: redis://localhost:6379/0
    ttl_seconds: 3600
    max_connections: 10
```

- `redis` package listed in `conf/requirements.txt` (currently commented)

### Required Implementation

**1. Redis Client Module** (`src/backend/redis_client.py`):

```python
import redis
from typing import Optional, Any
import json

class RedisClient:
    def __init__(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)

    def cache_metrics(self, run_id: str, metrics: dict, ttl: int = 3600):
        """Cache training metrics with TTL."""
        key = f"training:runs:{run_id}:metrics"
        self.client.setex(key, ttl, json.dumps(metrics))

    def get_metrics(self, run_id: str) -> Optional[dict]:
        """Retrieve cached metrics."""
        key = f"training:runs:{run_id}:metrics"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def stream_metrics(self, run_id: str, metrics: dict):
        """Append to metrics stream."""
        key = f"training:runs:{run_id}:stream"
        self.client.xadd(key, {"data": json.dumps(metrics)})
```

**2. Integration Points**:

- `src/backend/training_monitor.py`: Add Redis caching in metric callbacks
- `src/communication/websocket_manager.py`: Use Redis pub/sub for multi-instance coordination
- `src/main.py`: Initialize Redis client on startup, handle connection failures gracefully

**3. Key Patterns**:

- Metadata: `training:runs:<run_id>:meta`
- Metrics stream: `training:runs:<run_id>:stream` (Redis Streams)
- Latest snapshot: `training:latest` (hash)
- Session data: `session:<session_id>` (TTL: 24h)

**4. Deployment**:

- Standalone: `redis-server --port 6379 --appendonly yes`
- Docker: `docker-compose up redis` (see `conf/docker-compose.yaml`)
- Ubuntu systemd: `sudo systemctl start redis-server`

**5. Testing Requirements**:

- Mock Redis in unit tests using `fakeredis`
- Integration tests with real Redis container
- Performance tests for cache hit/miss latency

See `notes/Redis_deployment.md` for full deployment guide.

## Integration Points

- **CasCor Backend**: Located at `../cascor/`, integrated via dynamic import and method hooking
- **Redis Cache**: Port 6379, requires full implementation (see Redis Integration section above)
- **WebSocket Endpoints**:
  - **Primary**: `ws://localhost:8050/ws/training` - Live training metrics
  - **Control**: `ws://localhost:8050/ws/control` - Training control commands (TODO)
  - **Status**: `ws://localhost:8050/ws/status` - System health/status (TODO)
- **Static Files**: Served via FastAPI's `StaticFiles` mount (if configured)

## Design Documentation
Comprehensive design rationale in `notes/`:

- `architecture_design.md`: Technology stack analysis, system architecture diagrams
- `technical_specifications.md`: Component specs, data schemas, performance requirements
- `implementation_guide.md`: Step-by-step implementation, deployment, testing strategy
- `logging_framework_design.md`: Multi-level logging architecture details

## Testing Philosophy
Tests go in `src/tests/` with mocks, helpers, data, and reports. Pattern emphasizes:

- Unit tests for individual components
- Integration tests for CasCor hook installation
- Performance tests for WebSocket latency and dashboard update rates

**CRITICAL**: Test directory and comprehensive test suite must be created.

## Comprehensive Testing Framework (pytest)

### Directory Structure (To Be Created)

``` bash
src/tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures and configuration
├── pytest.ini                     # Pytest settings
├── unit/                          # Unit tests
│   ├── __init__.py
│   ├── test_config_manager.py
│   ├── test_logger.py
│   ├── test_data_adapter.py
│   ├── test_cascor_integration.py
│   └── test_websocket_manager.py
├── integration/                   # Integration tests
│   ├── __init__.py
│   ├── test_redis_integration.py
│   ├── test_cascor_backend.py
│   ├── test_websocket_flow.py
│   └── test_dashboard_rendering.py
├── performance/                   # Performance/load tests
│   ├── __init__.py
│   ├── test_websocket_latency.py
│   ├── test_metrics_throughput.py
│   └── test_dashboard_rendering_speed.py
├── mocks/                         # Mock objects and data
│   ├── __init__.py
│   ├── mock_cascor_network.py
│   ├── mock_redis_client.py
│   └── mock_training_data.py
├── helpers/                       # Test utilities
│   ├── __init__.py
│   ├── fixtures.py
│   ├── assertions.py
│   └── test_utils.py
├── data/                          # Test data files
│   ├── sample_configs.yaml
│   ├── training_metrics.json
│   └── network_topologies.json
└── reports/                       # Test output (auto-generated)
    ├── coverage/
    ├── junit/
    └── performance/
```

### Required Dependencies
Add to `conf/requirements.txt`:

``` bash
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
pytest-benchmark>=4.0.0
pytest-html>=3.2.0
fakeredis>=2.19.0
httpx>=0.24.0           # For FastAPI testing
```

### Core Test Configuration

**`src/tests/pytest.ini`**:

```ini
[pytest]
testpaths = src/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
adopts =
    --verbose
    --color=yes
    --cov=src
    --cov-report=html:src/tests/reports/coverage
    --cov-report=term-missing
    --junit-xml=src/tests/reports/junit/results.xml
    --html=src/tests/reports/test_report.html
    --self-contained-html
    --benchmark-only
    --benchmark-save=performance
asyncio_mode = auto
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow-running tests
    requires_redis: Tests requiring Redis connection
    requires_cascor: Tests requiring CasCor backend
```

**`src/tests/conftest.py`** (Fixtures):

```python
import pytest
import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from logging.logger import get_system_logger
from backend.redis_client import RedisClient
from fakeredis import FakeRedis

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return ConfigManager(config_path="src/tests/data/sample_configs.yaml")

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return FakeRedis(decode_responses=True)

@pytest.fixture
def mock_cascor_network():
    """Mock CasCor network instance."""
    from mocks.mock_cascor_network import MockCascorNetwork
    return MockCascorNetwork()

@pytest.fixture
def logger():
    """Provide test logger."""
    return get_system_logger()
```

### Example Test Files

**`src/tests/unit/test_config_manager.py`**:

```python
import pytest
from config_manager import ConfigManager

@pytest.mark.unit
class TestConfigManager:
    def test_load_config(self, test_config):
        """Test config loading."""
        assert test_config.get('application.name') is not None

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv('CASCOR_SERVER_PORT', '9999')
        config = ConfigManager()
        # Verify override applied

    def test_nested_access(self, test_config):
        """Test nested config access."""
        value = test_config.get('logging.console.level', 'INFO')
        assert value in ['DEBUG', 'INFO', 'WARNING', 'ERROR']
```

**`src/tests/integration/test_redis_integration.py`**:

```python
import pytest
from backend.redis_client import RedisClient

@pytest.mark.integration
@pytest.mark.requires_redis
class TestRedisIntegration:
    @pytest.fixture
    def redis_client(self, mock_redis):
        """Create Redis client with mock."""
        return RedisClient(url="redis://localhost:6379/0", client=mock_redis)

    def test_cache_metrics(self, redis_client):
        """Test metrics caching."""
        metrics = {"epoch": 1, "loss": 0.5, "accuracy": 0.9}
        redis_client.cache_metrics("test_run", metrics)

        retrieved = redis_client.get_metrics("test_run")
        assert retrieved == metrics

    def test_metrics_stream(self, redis_client):
        """Test metrics streaming."""
        for i in range(10):
            redis_client.stream_metrics("test_run", {"epoch": i})

        # Verify stream length
        assert len(redis_client.get_stream("test_run")) == 10
```

**`src/tests/performance/test_websocket_latency.py`**:

```python
import pytest
import asyncio
from communication.websocket_manager import WebSocketManager

@pytest.mark.performance
class TestWebSocketPerformance:
    @pytest.mark.asyncio
    async def test_message_latency(self, benchmark):
        """Benchmark WebSocket message latency."""
        ws_manager = WebSocketManager()

        async def send_message():
            await ws_manager.broadcast({"test": "data"})

        # Should be < 10ms
        result = await benchmark(send_message)
        assert result < 0.010  # 10ms
```

### Command-Line Testing

**Run all tests**:

```bash
conda activate JuniperCanopy
cd src/tests
pytest
```

**Run specific test categories**:

```bash
pytest -m unit                    # Unit tests only
pytest -m integration             # Integration tests only
pytest -m performance             # Performance tests only
pytest -m "not slow"              # Exclude slow tests
```

**Coverage report**:

```bash
pytest --cov=src --cov-report=html
# View: open src/tests/reports/coverage/index.html
# Run `pytest --cov=src --cov-report=html` to generate the report
```

**Parallel execution**:

```bash
pip install pytest-xdist
pytest -n auto  # Use all CPU cores
```

### VS Code Integration

**`.vscode/settings.json`** (add to workspace):

```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.pytestArgs": [
        "src/tests"
    ],
    "python.testing.cwd": "${workspaceFolder}",
    "python.testing.autoTestDiscoverOnSaveEnabled": true,
    "coverage-gutters.coverageFileNames": [
        "src/tests/reports/coverage/coverage.xml"
    ]
}
```

**Install VS Code Extensions**:

- Python Test Explorer
- Coverage Gutters (for inline coverage)
- Test Explorer UI

**Run tests in VS Code**:

1. Open Testing sidebar (beaker icon)
2. Tests auto-discovered from `src/tests/`
3. Click play button to run individual tests
4. View results inline with code coverage highlights

### Continuous Testing Workflow

**Watch mode** (auto-run on file changes):

```bash
pip install pytest-watch
ptw src/tests -- --testmon  # Only run affected tests
```

**Pre-commit hook** (`.git/hooks/pre-commit`):

```bash
#!/usr/bin/env bash
conda activate JuniperCanopy
pytest src/tests/unit -x  # Stop on first failure
if [ $? -ne 0 ]; then
    echo "Unit tests failed. Commit aborted."
    exit 1
fi
```

### Test Coverage Requirements

- **Target**: 90% coverage (`development.testing.coverage_threshold: 0.9` in config)
- **Critical paths**: 100% coverage required for:
  - `src/config_manager.py`
  - `src/backend/cascor_integration.py`
  - `src/communication/websocket_manager.py`
  - `src/logging/logger.py`

### Test Data Generation

**Script**: `src/tests/helpers/generate_test_data.py`

```python
#!/usr/bin/env python
"""Generate synthetic test data."""
import json
import numpy as np

def generate_training_metrics(epochs=100):
    """Generate fake training metrics."""
    return [{
        "epoch": i,
        "loss": 1.0 / (i + 1) + np.random.normal(0, 0.1),
        "accuracy": (i / epochs) * 0.95 + np.random.normal(0, 0.02)
    } for i in range(epochs)]

if __name__ == "__main__":
    data = generate_training_metrics()
    with open("src/tests/data/training_metrics.json", "w") as f:
        json.dump(data, f, indent=2)
```

## Docker Deployment

### Multi-Stage Build Strategy
The `conf/Dockerfile` uses Python 3.9 slim base. For production:

**Build image**:

```bash
cd /path/to/juniper_canopy
docker build -f conf/Dockerfile -t juniper_canopy:latest .
```

**Standalone run**:

```bash
docker run -d \
    --name juniper-canopy \
    -p 8050:8050 \
    -e CASCOR_BACKEND_PATH=/app/cascor \
    -e CASCOR_ENV=production \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/data:/app/data \
    juniper_canopy:latest
```

### Docker Compose Orchestration

**Full stack** (Frontend + Redis + optional CasCor backend):

```bash
cd /path/to/juniper_canopy
docker-compose -f conf/docker-compose.yaml up -d
```

**Stack includes**:

- `juniper-canopy`: Main application (port 8050)
- `redis`: Redis 7 Alpine with persistence (port 6379)
- `juniper_cascor:  the CasCor NN backend`: (Optional) CasCor network service (port 8000)

**Environment variables** (create `.env` in project root):

```bash
CASCOR_ENV=production
CASCOR_DEBUG=false
REDIS_URL=redis://redis:6379/0
CASCOR_BACKEND_URL=http://cascor-backend:8000
JWT_SECRET_KEY=your-secret-key-here
```

**Service management**:

```bash
docker-compose -f conf/docker-compose.yaml ps        # Status
docker-compose -f conf/docker-compose.yaml logs -f   # Follow logs
docker-compose -f conf/docker-compose.yaml down      # Stop all
docker-compose -f conf/docker-compose.yaml restart juniper_canopy  # Restart service
```

**Volume persistence**:

- `redis-data`: Redis persistent storage
- `../logs`: Application logs (mounted from host)
- `../data`: Datasets (mounted from host)
- `../images`: Generated visualizations (mounted from host)

### Production Deployment Checklist

1. **Build optimized image**: `docker build --target production ...`
2. **Security hardening**:
    - Set `protected-mode yes` in Redis config
    - Enable authentication: `conf/app_config.yaml` → `security.authentication.enabled: true`
    - Configure CORS allowed origins (not `*`)
    - Use secrets management (not env vars for passwords)
3. **Resource limits** (docker-compose.yaml):

    ```yaml
    services:
        juniper-canopy:
            deploy:
                resources:
                    limits:
                        cpus: '2.0'
                        memory: 1G
    ```

4. **Health checks**: Enabled in Dockerfile (`/health` endpoint)
5. **Monitoring**: Add Prometheus metrics exporter
6. **Backup strategy**: Redis RDB snapshots, log rotation

### Ubuntu 25.04 Systemd Service (Alternative to Docker)

**Create service**: `/etc/systemd/system/juniper-canopy.service`

```ini
[Unit]
Description=Juniper Canopy Service
After=network.target redis.service

[Service]
Type=simple
User=pcalnon
Group=pcalnon
WorkingDirectory=/home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/src
Environment="PATH=/home/pcalnon/miniconda3/envs/JuniperPython/bin"
Environment="CASCOR_BACKEND_PATH=/home/pcalnon/Development/python/JuniperCascor/juniper_cascor/src"
ExecStart=/home/pcalnon/miniconda3/envs/JuniperPython/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable juniper-canopy
sudo systemctl start juniper-canopy
sudo systemctl status juniper-canopy
```

**Critical**: When creating new files, always place them in the appropriate directory:

- Configuration → `conf/`
- Documentation/design → `notes/`
- Source code → `src/` (create subdirectories as needed)

## Key Project Requirements

The frontend must support:

1. **Real-time training monitoring** - Live updates during neural network training
2. **Performance statistics** - Metrics visualization and tracking
3. **Dataset plotting** - Visual representation of training/test data
4. **Decision boundaries** - Graphical display of learned decision regions
5. **Network visualization** - Interactive representation of the CasCor architecture

## Development Workflow

Based on the prompt requirements, when implementing features:

1. **Break complex problems into sub-problems** - Use systematic decomposition
2. **Maintain detailed task tracking** - Document steps taken and assumptions made
3. **Provide thorough documentation** - Include references and design rationale
4. **Follow logical progression** - Work step-by-step through implementation

## Technology Considerations

The project requires careful selection of:

- **Visualization frameworks** for real-time neural network monitoring
- **Communication protocols** between Python backend and frontend
- **Plotting libraries** for data visualization and decision boundaries
- **UI frameworks** that integrate well with scientific Python ecosystem

## Coding Patterns

- **Modularity**: Design for flexible, maintainable, and scalable solutions
- **Real-time capabilities**: Consider WebSocket or similar for live updates
- **Scientific visualization**: Leverage established libraries (matplotlib, plotly, bokeh)
- **Cross-platform compatibility**: Ensure Ubuntu/conda environment compatibility

## AI Agent Guidelines

- Always check the project structure before creating files
- Reference the original requirements in `prompts/prompt_juniper_canopy.md`
- Consider the neural network domain context when suggesting implementations
- Prioritize maintainability and scalability in architectural decisions
- Document assumptions and provide implementation rationale

## Key Insights Captured

1. **Project Context**: This is a prototype for visualizing Cascade Correlation neural networks, which is a specialized domain requiring real-time monitoring capabilities. The Cascade Correlation network that this frontend is intended to monitor when completed is another prototype defined in the `JuniperCascor/juniper_cascor` directory.

2. **Strict Directory Organization**: The project follows a specific directory pattern that must be maintained for all new files:

    - `conf/` - Configuration files (conda envs, app configs)
    - `notes/` - Documentation, procedures, todos, design docs
    - `prompts/` - AI prompts and project requirements
    - `src/` - All source code (organized in subdirectories)
    - `data/` - Multiple datasets with additional child directories
    - `docs/` - Copies of reference sources with URLs and links to references
    - `images/` - Static images generated by the application
    - `logs/` - All log files
    - `util/` - Utility, environment, management, and cleanup scripts
    - `src/tests/` - All testing resources including unit and integration test source files, scripts, reports, mocks, helpers, config, data, and documentation

3. **Development Environment**: Ubuntu/conda/VS Code stack with Python backend and frontend technology to be determined.

4. **Core Requirements**: Real-time training monitoring, performance stats, dataset plotting, decision boundaries, network visualization, and robust logging to console and to disk with independently controlled log levels.

5. **Methodical Approach**: Emphasis on breaking complex problems into sub-problems and maintaining detailed documentation.
