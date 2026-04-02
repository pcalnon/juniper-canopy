# AGENTS.md Drift Analysis

**Date**: 2026-04-02
**Version**: 1.0.0
**Status**: Current
**Scope**: Comprehensive audit of AGENTS.md (v0.3.0) against juniper-canopy application state (v0.4.0)

---

## Executive Summary

The juniper-canopy AGENTS.md file has accumulated significant drift from the actual application state.
The application has undergone major architectural changes — most notably:

- A migration from the legacy `CASCOR_*` environment variable prefix to `JUNIPER_CANOPY_*` via Pydantic BaseSettings
- A refactoring of the backend from a monolithic `cascor_integration.py` to a multi-module backend with protocol-based architecture
- The addition of numerous new source modules, API endpoints, frontend components, and infrastructure features

The AGENTS.md still reflects the pre-refactor state in many critical areas.

**Severity**: HIGH — Multiple sections contain incorrect file references, outdated configuration guidance, and missing architectural components that could mislead developers and AI agents working on the codebase.

---

## Drift Findings by Section

### 1. Version Number (CRITICAL)

| Area | AGENTS.md | Actual |
|------|-----------|--------|
| Version | 0.3.0 | 0.4.0 (pyproject.toml) |

**Impact**: Agents may not recognize that the application has evolved past the documented version.

---

### 2. Environment Variable Prefix (CRITICAL)

**AGENTS.md State**: Extensively documents `CASCOR_*` prefix as the primary configuration mechanism throughout multiple sections (Configuration Management, Environment Variable Overrides, Demo Mode, etc.).

**Actual State**: The application has migrated to `JUNIPER_CANOPY_*` prefix via Pydantic BaseSettings (`src/settings.py`, line 110: `env_prefix="JUNIPER_CANOPY_"`). Legacy `CASCOR_*` variables are supported with deprecation warnings.

**Affected Sections**:

- "Configuration Hierarchy" (line 438-444): States "Environment Variables (CASCOR_*)"
- "Server Configuration" (lines 452-456): Documents `CASCOR_SERVER_HOST`, `CASCOR_SERVER_PORT`, etc.
- "Training Parameters" (lines 460-463): Documents `CASCOR_TRAINING_EPOCHS`, etc.
- "Backend Integration" (lines 477-479): Documents `CASCOR_BACKEND_PATH`
- "WebSocket Configuration" (lines 483-487): Documents `CASCOR_WEBSOCKET_*`
- "Demo Mode" (lines 491-494): Documents `CASCOR_DEMO_UPDATE_INTERVAL`
- "Environment Setup" (lines 775-782): Documents `CASCOR_<SECTION>_<KEY>` format
- "Demo Mode vs Real Backend" (lines 334-367): References `CASCOR_DEMO_MODE` and `CASCOR_BACKEND_PATH`
- "Path and Environment Configuration" (lines 1058-1073)
- "Configuration Troubleshooting" (lines 594-624)
- All code examples using `os.getenv("CASCOR_*")`

**Impact**: HIGH — Developers following the documented env vars would use deprecated patterns.

---

### 3. Configuration Architecture (HIGH)

**AGENTS.md State**: Documents a three-level hierarchy: "env vars (CASCOR_*) > YAML (conf/app_config.yaml) > constants (canopy_constants.py)" with manual `os.getenv()` + ConfigManager pattern.

**Actual State**: The application now uses Pydantic BaseSettings (`src/settings.py`) as the primary configuration system with:

- Structured, typed settings with validation
- Nested model hierarchy (ServerSettings, TrainingSettings, WebSocketSettings, etc.)
- Automatic env var parsing with `JUNIPER_CANOPY_` prefix
- Double-underscore nesting (e.g., `JUNIPER_CANOPY_SERVER__PORT`)
- `pydantic-settings>=2.0.0` as a core dependency
- Legacy CASCOR_* support with deprecation warnings

The ConfigManager (`src/config_manager.py`) is now documented as "legacy/deprecated" in the architecture analysis.

**Impact**: HIGH — Code examples in AGENTS.md show outdated configuration patterns.

---

### 4. Backend Architecture — Missing File (CRITICAL)

**AGENTS.md State**: References `src/backend/cascor_integration.py` (line 328) with description of `CascorIntegration` class.

**Actual State**: This file **does not exist**. The backend has been refactored into a multi-module architecture:

| Actual File | Purpose |
|-------------|---------|
| `src/backend/__init__.py` | Backend factory (`create_backend`) |
| `src/backend/protocol.py` | `BackendProtocol` typing interface |
| `src/backend/demo_backend.py` | `DemoBackend` (wraps DemoMode) |
| `src/backend/service_backend.py` | `ServiceBackend` (wraps CascorServiceAdapter) |
| `src/backend/cascor_service_adapter.py` | juniper-cascor-client wrapper |
| `src/backend/circuit_breaker.py` | Fault tolerance |
| `src/backend/cassandra_client.py` | Optional Cassandra integration |
| `src/backend/redis_client.py` | Optional Redis caching |
| `src/backend/data_adapter.py` | Data normalization |
| `src/backend/training_monitor.py` | Metrics collection (TrainingState) |
| `src/backend/training_state_machine.py` | FSM for training control |
| `src/backend/state_sync.py` | State synchronization |
| `src/backend/statistics.py` | Statistics module |

**Impact**: CRITICAL — Reference to non-existent file will cause confusion for any agent following the documentation.

---

### 5. Source Module Inventory — Missing Modules (HIGH)

**AGENTS.md Directory Structure** (lines 248-298) omits these source files:

| Missing File | Purpose |
|-------------|---------|
| `src/settings.py` | Pydantic BaseSettings configuration |
| `src/discovery.py` | Auto-discovery of cascor instances |
| `src/health.py` | Health check probes (/v1/health/*) |
| `src/middleware.py` | Security, rate limiting, CSP headers |
| `src/observability.py` | Sentry, Prometheus, request ID middleware |
| `src/security.py` | API key auth, rate limiting |
| `src/secrets_util.py` | Environment secret management |

**Impact**: Agents working on these files will have no guidance from AGENTS.md.

---

### 6. Frontend Components — Missing Components (HIGH)

**AGENTS.md** only implicitly references frontend components. The actual component list includes many undocumented modules:

| Missing Component | File |
|------------------|------|
| About Panel | `src/frontend/components/about_panel.py` |
| Candidate Metrics Panel | `src/frontend/components/candidate_metrics_panel.py` |
| Cassandra Panel | `src/frontend/components/cassandra_panel.py` |
| HDF5 Snapshots Panel | `src/frontend/components/hdf5_snapshots_panel.py` |
| Parameters Panel | `src/frontend/components/parameters_panel.py` |
| Redis Panel | `src/frontend/components/redis_panel.py` |
| Training Metrics | `src/frontend/components/training_metrics.py` |
| Tutorial Panel | `src/frontend/components/tutorial_panel.py` |
| Worker Panel | `src/frontend/components/worker_panel.py` |
| Base Component | `src/frontend/base_component.py` |
| Callback Context | `src/frontend/callback_context.py` |
| Tooltips | `src/frontend/tooltips.py` |

---

### 7. API Endpoints — Incomplete Documentation (HIGH)

**AGENTS.md** (lines 955-966) only documents 5 key endpoints. The actual application exposes 30+ REST endpoints and 3 WebSocket endpoints:

**Missing REST Endpoints**:

- Health probes: `/v1/health`, `/v1/health/live`, `/v1/health/ready`
- State/status: `/api/state`, `/api/status`
- Network: `/api/topology`, `/api/topology/raw`, `/api/statistics`
- Snapshots: `/api/v1/snapshots/*` (CRUD + restore)
- Metrics Layouts: `/api/v1/metrics/layouts/*` (CRUD)
- Infrastructure: `/api/v1/redis/*`, `/api/v1/cassandra/*`, `/api/v1/workers/*`
- Training control: `/api/train/start`, `/api/train/pause`, `/api/train/resume`, `/api/train/stop`, `/api/train/reset`, `/api/set_params`
- Remote workers: `/api/remote/*`
- Dataset: `/api/dataset/generate`

**Missing WebSocket Endpoints**:

- `/ws` (legacy endpoint) not documented

---

### 8. Test Markers — Incomplete (MEDIUM)

**AGENTS.md** (lines 113-127) lists 10 markers. `pyproject.toml` defines 13:

| Missing Marker | Description |
|---------------|-------------|
| `requires_cassandra` | Tests requiring Cassandra connection |
| `api` | Tests for API endpoints |
| `generators` | Tests for data generators |

---

### 9. Test Fixtures — Incomplete (MEDIUM)

**AGENTS.md** (lines 165-187) documents 5 fixtures. The actual `conftest.py` (730 lines) defines 14+:

| Missing Fixture | Scope | Purpose |
|----------------|-------|---------|
| `mock_juniper_data_client` | session, autouse | Mocks JuniperDataClient with realistic spiral data |
| `test_config` | function | Safe defaults for application config |
| `preserve_metrics_layouts` | session, autouse | Backs up/restores metrics_layouts.json |
| `cleanup_test_environment` | function, autouse | Clears test env vars |
| `mock_config_file` | function | Temporary YAML config |
| `temp_test_directory` | function | Temporary test directory |

The `reset_singletons` fixture description is also outdated — it now also resets `Settings` and security state.

---

### 10. Constants Import Path (MEDIUM)

**AGENTS.md** (line 404): `from constants import TrainingConstants, DashboardConstants`

**Actual**: `from canopy_constants import TrainingConstants, DashboardConstants`

The file is named `canopy_constants.py`, not `constants.py`.

---

### 11. Conda Environment Name (MEDIUM)

**AGENTS.md** (lines 755-766): References `/opt/miniforge3/envs/JuniperCanopy`

**Parent CLAUDE.md**: References `JuniperPython` as the conda env for juniper-canopy.

**`conf/conda_environment.yaml`**: Does not specify an explicit env name.

**Impact**: Inconsistent naming across documentation layers.

---

### 12. Directory Structure — Docs Organization (MEDIUM)

**AGENTS.md** (lines 1098-1168) places several documentation files at the project root:

- `QUICK_START.md`, `ENVIRONMENT_SETUP.md`, `DOCUMENTATION_OVERVIEW.md`

**Actual**: These files exist in `docs/` subdirectory, not project root.

**AGENTS.md** references `docs/phase0-3/` directories. **Actual**: Phase directories are in `notes/development/phase{0-3}/` and `notes/integration/phase_{0-5}/`.

---

### 13. docs/ Subdirectory — Missing Categories (MEDIUM)

**AGENTS.md** does not document:

- `docs/deployment/` (contains Kubernetes deployment plan)
- `docs/testing/ADR_001_VALID_TEST_SKIPS.md`
- `docs/testing/SELECTIVE_TEST_GUIDE.md`
- `docs/testing/TEST_ENABLEMENT_QUICK_REFERENCE.md`

---

### 14. notes/ Subdirectory Structure (MEDIUM)

**AGENTS.md** gives minimal detail about the `notes/` organization. The actual structure includes rich subdirectories:

```text
notes/
├── analysis/           # Technical analyses
├── development/        # Dev roadmaps and phase work
│   ├── phase0-3/       # Development phase READMEs
├── fixes/              # Bug fix plans and reports
├── history/            # Historical analyses and audits
├── integration/        # Integration phase analysis (phases 0-5)
├── mcp/                # MCP server setup guides
├── pull_requests/      # PR descriptions
├── releases/           # Release notes (v0.14.0 - v0.25.0)
├── research/           # Research proposals
└── templates/          # Issue, PR, release note templates
```

---

### 15. Root-Level Files — Missing (LOW)

**AGENTS.md** directory structure omits:

- `CHANGELOG.md` (125,622 bytes)
- `Dockerfile` (root-level)
- `LICENSE`
- `.env.dev`, `.env.example`, `.env.prod`
- `requirements.lock`
- `.mcp.json` (MCP server configuration)
- `.serena/` directory
- Various symlinks (`conda_environment.yaml`, `tests`, `try`, `demo`)

---

### 16. Scripts Directory — Not Fully Documented (LOW)

**AGENTS.md** mentions `util/` for utility scripts but does not document the `scripts/` directory:

- `scripts/generate_dep_docs.sh`
- `scripts/juniper-canopy.service` (systemd service)
- `scripts/juniper-ctl` (control utility)

---

### 17. GitHub Workflows — Incomplete (LOW)

**AGENTS.md** does not document the full set of CI/CD workflows:

- `ci.yml` — CI pipeline
- `lockfile-update.yml` — Dependency lock automation
- `publish.yml` — Publishing/release
- `security-scan.yml` — Security scanning

---

### 18. Recent Changes — Stale (LOW)

**AGENTS.md** last "Recent Changes" entry is dated 2026-02-05. Significant work has occurred since:

- Demo training stall root cause analysis (2026-03-19)
- Candidate quality degradation analysis (2026-03-19)
- Meta Parameters enhancement planning (2026-03-21)
- Pre-commit lint failure analysis (2026-03-31)
- 35 failing tests analysis (2026-04-02)

---

### 19. Docker Section — Outdated (LOW)

**AGENTS.md** (line 949): Documents Docker as "Docker (Future)" with `docker-compose up`.

**Actual**: Docker is implemented. `Dockerfile` exists at root level AND in `conf/`. `conf/docker-compose.yaml` exists.

---

### 20. MCP Server Availability (LOW)

**AGENTS.md** contains no reference to MCP server configuration or availability. The project has:

- `.mcp.json` with Exa API integration
- `notes/mcp/` with setup guides for Serena, AlphaVantage, and Exa

---

## Drift Summary Matrix

| # | Section | Severity | Lines Affected | Change Type |
|---|---------|----------|---------------|-------------|
| 1 | Version number | CRITICAL | 3 | Update |
| 2 | Env var prefix | CRITICAL | 50+ | Rewrite |
| 3 | Configuration architecture | HIGH | 100+ | Rewrite |
| 4 | Backend file reference | CRITICAL | 328 | Fix |
| 5 | Missing source modules | HIGH | 248-298 | Add |
| 6 | Missing frontend components | HIGH | 301-327 | Add |
| 7 | API endpoints | HIGH | 955-966 | Expand |
| 8 | Test markers | MEDIUM | 113-127 | Add |
| 9 | Test fixtures | MEDIUM | 165-187 | Expand |
| 10 | Constants import path | MEDIUM | 404 | Fix |
| 11 | Conda env name | MEDIUM | 755-766 | Verify/Fix |
| 12 | Docs organization | MEDIUM | 1098-1168 | Fix |
| 13 | Missing docs categories | MEDIUM | 1136-1153 | Add |
| 14 | Notes structure | MEDIUM | 1160-1168 | Expand |
| 15 | Missing root files | LOW | 248-298 | Add |
| 16 | Scripts directory | LOW | 294 | Add |
| 17 | GitHub workflows | LOW | 213-227 | Expand |
| 18 | Recent Changes stale | LOW | 2232+ | Update |
| 19 | Docker section | LOW | 947-951 | Update |
| 20 | MCP availability | LOW | N/A | Add |

**Total Drift Items**: 20

- CRITICAL: 3
- HIGH: 4
- MEDIUM: 6
- LOW: 7

---

## Recommendations

1. **Immediate**: Fix all CRITICAL items (version, env vars, non-existent file reference)
2. **High Priority**: Rewrite Configuration Management and Backend Architecture sections
3. **Medium Priority**: Expand test documentation, fix docs/notes organization references
4. **Low Priority**: Update Recent Changes, add MCP references, expand workflow docs
5. **Structural**: Consider whether the "Recent Changes" section should be trimmed to last 3-5 entries with older entries moved to CHANGELOG.md
