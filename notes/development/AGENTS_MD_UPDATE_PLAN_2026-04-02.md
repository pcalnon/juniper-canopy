# AGENTS.md Update Plan

**Date**: 2026-04-02
**Version**: 1.0.0
**Status**: Current
**Input**: [AGENTS_MD_DRIFT_ANALYSIS_2026-04-02.md](../analysis/AGENTS_MD_DRIFT_ANALYSIS_2026-04-02.md)

---

## Objective

Bring the juniper-canopy AGENTS.md file into alignment with the application's current state (v0.4.0), ensuring accuracy of all technical references, configuration guidance, architecture documentation, and developer workflows.

---

## Phase 1: Critical Fixes (Blocking — Must Fix First)

### Step 1.1: Update Version Number

- **Task**: Change AGENTS.md version from `0.3.0` to `0.4.0`
- **Location**: Line 3
- **Effort**: Trivial

### Step 1.2: Fix Non-Existent File Reference

- **Task**: Replace `src/backend/cascor_integration.py` reference with accurate backend architecture
- **Location**: Line 328 (Key Components section)
- **Effort**: Moderate — requires rewriting the component description to reflect the protocol-based multi-module architecture

### Step 1.3: Fix Constants Import Path

- **Task**: Change `from constants import` to `from canopy_constants import` in all code examples
- **Location**: Lines 404-408
- **Effort**: Trivial

---

## Phase 2: Configuration Architecture Rewrite (High Priority)

### Step 2.1: Rewrite Configuration Hierarchy Section

- **Task**: Document Pydantic BaseSettings as primary config system; demote CASCOR_* to legacy
- **Scope**: Lines 436-597 (Configuration Management through Configuration Troubleshooting)
- **New content**:
  - Primary: Pydantic BaseSettings via `settings.py` with `JUNIPER_CANOPY_*` prefix
  - Secondary: YAML configuration via `conf/app_config.yaml`
  - Tertiary: Constants module via `canopy_constants.py`
  - Legacy: `CASCOR_*` env vars with deprecation warnings
- **Effort**: Major rewrite

### Step 2.2: Update Environment Variable Documentation

- **Task**: Replace all `CASCOR_*` env var examples with `JUNIPER_CANOPY_*` equivalents
- **Scope**: Server Configuration, Training Parameters, WebSocket Configuration, Demo Mode sections
- **Include**: Double-underscore nesting syntax (e.g., `JUNIPER_CANOPY_SERVER__PORT`)
- **Effort**: Major rewrite

### Step 2.3: Update Demo Mode Section

- **Task**: Update demo mode activation to reference `JUNIPER_CANOPY_DEMO_MODE`
- **Scope**: Lines 334-367 (Demo Mode vs Real Backend)
- **Note**: Keep backward-compatibility mention of legacy `CASCOR_DEMO_MODE`
- **Effort**: Moderate

### Step 2.4: Update Code Examples

- **Task**: Replace all configuration code examples showing manual `os.getenv("CASCOR_*")` patterns with Pydantic Settings usage
- **Scope**: Lines 546-563 and similar
- **Effort**: Moderate

---

## Phase 3: Architecture Documentation Update (High Priority)

### Step 3.1: Update Directory Structure

- **Task**: Add missing source files to directory tree
- **Files to add**: `settings.py`, `discovery.py`, `health.py`, `middleware.py`, `observability.py`, `security.py`, `secrets_util.py`
- **Backend files**: Replace `cascor_integration.py` with actual 12-file backend structure
- **Frontend files**: Add all component files, `base_component.py`, `callback_context.py`, `tooltips.py`
- **Root files**: Add `CHANGELOG.md`, `Dockerfile`, `LICENSE`, `.env.*` files
- **Scope**: Lines 248-298
- **Effort**: Major update

### Step 3.2: Rewrite Key Components Section

- **Task**: Replace monolithic CascorIntegration description with actual architecture
- **New components to document**:
  1. FastAPI Backend (`src/main.py`)
  2. Pydantic Settings (`src/settings.py`)
  3. Dash Dashboard (`src/frontend/dashboard_manager.py`)
  4. Demo Mode (`src/demo_mode.py`)
  5. Backend Protocol & Factory (`src/backend/protocol.py`, `src/backend/__init__.py`)
  6. Service Backend (`src/backend/service_backend.py`)
  7. Demo Backend (`src/backend/demo_backend.py`)
  8. CasCor Service Adapter (`src/backend/cascor_service_adapter.py`)
  9. WebSocket Manager (`src/communication/websocket_manager.py`)
  10. Training State Machine (`src/backend/training_state_machine.py`)
  11. Health Probes (`src/health.py`)
  12. Observability (`src/observability.py`)
  13. Constants Module (`src/canopy_constants.py`)
- **Scope**: Lines 301-332
- **Effort**: Major rewrite

### Step 3.3: Expand API Endpoints Documentation

- **Task**: Document all REST endpoints and WebSocket endpoints
- **Scope**: Lines 953-998
- **Organize by**: Health/Status, Training Control, Metrics, Network/Topology, Snapshots, Infrastructure, Remote Workers, WebSocket
- **Effort**: Major expansion

---

## Phase 4: Test Documentation Update (Medium Priority)

### Step 4.1: Add Missing Test Markers

- **Task**: Add `requires_cassandra`, `api`, `generators` to marker table
- **Scope**: Lines 113-127
- **Effort**: Trivial

### Step 4.2: Expand Test Fixtures Documentation

- **Task**: Document all major fixtures from the 730-line conftest.py
- **Add**: `mock_juniper_data_client`, `test_config`, `preserve_metrics_layouts`, `cleanup_test_environment`, updated `reset_singletons`
- **Scope**: Lines 165-187
- **Effort**: Moderate

### Step 4.3: Update Test Environment Variables

- **Task**: Add `CASSANDRA_INTEGRATION_TEST`, `JUNIPER_DATA_E2E_TEST`, `REDIS_INTEGRATION_TEST` to env var table
- **Scope**: Lines 142-162
- **Effort**: Trivial

---

## Phase 5: Documentation Organization Update (Medium Priority)

### Step 5.1: Fix Documentation File Locations

- **Task**: Correct references to root-level docs (QUICK_START.md, etc.) to reflect actual `docs/` location
- **Scope**: Lines 1098-1168
- **Effort**: Moderate

### Step 5.2: Update notes/ Structure Documentation

- **Task**: Document actual notes/ subdirectory structure
- **Scope**: Lines 1160-1168
- **Effort**: Moderate

### Step 5.3: Update docs/ Subdirectory References

- **Task**: Add `docs/deployment/`, update testing docs references
- **Scope**: Lines 1136-1153
- **Effort**: Trivial

---

## Phase 6: Low-Priority Updates

### Step 6.1: Update Docker Section

- **Task**: Remove "Future" label; document actual Docker support
- **Scope**: Lines 947-951
- **Effort**: Trivial

### Step 6.2: Update GitHub Workflows

- **Task**: Document all 4 workflow files
- **Scope**: Lines 213-227
- **Effort**: Trivial

### Step 6.3: Add MCP Server Section

- **Task**: Add section documenting MCP server availability and configuration
- **Scope**: New section
- **Effort**: Moderate

### Step 6.4: Add scripts/ Directory Documentation

- **Task**: Document scripts/ directory contents
- **Scope**: Directory structure section
- **Effort**: Trivial

### Step 6.5: Trim Recent Changes Section

- **Task**: Keep last 3-5 recent changes; move older entries to CHANGELOG.md references
- **Scope**: Lines 2232+
- **Effort**: Moderate

### Step 6.6: Fix Conda Environment References

- **Task**: Verify and correct conda environment name references
- **Scope**: Lines 755-766
- **Effort**: Trivial

---

## Validation Plan

After completing all phases:

1. **File reference validation**: Verify every file path referenced in AGENTS.md exists
2. **Import path validation**: Verify all code examples use correct import paths
3. **Env var validation**: Grep codebase to confirm all documented env vars are correct
4. **Endpoint validation**: Cross-reference documented endpoints against `src/main.py`
5. **Test marker validation**: Cross-reference against `pyproject.toml` markers
6. **Fixture validation**: Cross-reference against `src/tests/conftest.py`
7. **Markdown link validation**: Ensure all internal links resolve

---

## Estimated Scope

| Phase | Items | Effort | Priority |
|-------|-------|--------|----------|
| Phase 1 | 3 | Small | CRITICAL |
| Phase 2 | 4 | Large | HIGH |
| Phase 3 | 3 | Large | HIGH |
| Phase 4 | 3 | Medium | MEDIUM |
| Phase 5 | 3 | Medium | MEDIUM |
| Phase 6 | 6 | Small-Medium | LOW |

**Total**: ~22 discrete tasks across 6 phases
