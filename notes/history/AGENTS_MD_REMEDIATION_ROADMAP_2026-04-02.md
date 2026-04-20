# AGENTS.md Remediation Development Roadmap

**Date**: 2026-04-02
**Version**: 1.0.0
**Status**: Current
**Input**: [AGENTS_MD_DRIFT_ANALYSIS_2026-04-02.md](../analysis/AGENTS_MD_DRIFT_ANALYSIS_2026-04-02.md), [AGENTS_MD_UPDATE_PLAN_2026-04-02.md](AGENTS_MD_UPDATE_PLAN_2026-04-02.md)

---

## Roadmap Overview

This roadmap defines all work items required to remediate AGENTS.md drift, organized as prioritized phases with discrete, actionable tasks.

---

## Phase 1: Critical Path Fixes

**Priority**: P0 — Blocking
**Goal**: Eliminate all references to non-existent files and critically incorrect information

| ID | Task | Status | File(s) | Change |
|----|------|--------|---------|--------|
| R-001 | Update AGENTS.md version to 0.4.0 | NOT STARTED | AGENTS.md:3 | `0.3.0` -> `0.4.0` |
| R-002 | Replace `cascor_integration.py` reference with actual backend modules | NOT STARTED | AGENTS.md:328 | Rewrite component #6 |
| R-003 | Fix constants import path in code examples | NOT STARTED | AGENTS.md:404 | `from constants` -> `from canopy_constants` |

---

## Phase 2: Configuration System Overhaul

**Priority**: P1 — High
**Goal**: Rewrite all configuration documentation to reflect Pydantic BaseSettings migration

| ID | Task | Status | Section | Change |
|----|------|--------|---------|--------|
| R-004 | Rewrite Configuration Hierarchy description | NOT STARTED | Configuration Management | New: Pydantic Settings > YAML > Constants; Legacy CASCOR_* deprecated |
| R-005 | Rewrite Server Configuration env vars | NOT STARTED | Server Configuration | `CASCOR_SERVER_*` -> `JUNIPER_CANOPY_SERVER__*` |
| R-006 | Rewrite Training Parameters env vars | NOT STARTED | Training Parameters | `CASCOR_TRAINING_*` -> `JUNIPER_CANOPY_TRAINING__*` |
| R-007 | Rewrite WebSocket Configuration env vars | NOT STARTED | WebSocket Configuration | `CASCOR_WEBSOCKET_*` -> `JUNIPER_CANOPY_WEBSOCKET__*` |
| R-008 | Rewrite Demo Mode env vars | NOT STARTED | Demo Mode | `CASCOR_DEMO_*` -> `JUNIPER_CANOPY_DEMO_*` |
| R-009 | Rewrite Backend Integration env vars | NOT STARTED | Backend Integration | `CASCOR_BACKEND_PATH` -> `JUNIPER_CANOPY_BACKEND_PATH` |
| R-010 | Update Demo Mode vs Real Backend section | NOT STARTED | Demo Mode vs Real Backend | `CASCOR_DEMO_MODE` -> `JUNIPER_CANOPY_DEMO_MODE` |
| R-011 | Rewrite configuration code examples | NOT STARTED | Using Configuration in Code | Replace os.getenv/ConfigManager with Settings pattern |
| R-012 | Update Configuration Troubleshooting | NOT STARTED | Configuration Troubleshooting | Update prefix references |
| R-013 | Update Path and Environment Configuration | NOT STARTED | Path and Environment Rules | Update env var format |
| R-014 | Update Environment Setup section | NOT STARTED | Environment Setup | Update env var format, verify conda env name |
| R-015 | Add legacy env var deprecation notice | NOT STARTED | Configuration Management | New subsection documenting backward-compatible CASCOR_* support |

---

## Phase 3: Architecture Documentation

**Priority**: P1 — High
**Goal**: Accurately reflect the current application architecture

| ID | Task | Status | Section | Change |
|----|------|--------|---------|--------|
| R-016 | Update directory structure tree | NOT STARTED | Directory Structure | Add 7 missing src modules, 12 backend files, 12 frontend files, root files |
| R-017 | Rewrite Key Components section | NOT STARTED | Key Components | Replace 6 components with 13 accurate components |
| R-018 | Expand REST API endpoint documentation | NOT STARTED | REST API Endpoints | Document all 30+ endpoints organized by category |
| R-019 | Update WebSocket channel documentation | NOT STARTED | WebSocket Channels | Add `/ws` legacy endpoint, expand descriptions |
| R-020 | Update AI Agent Quick Start checklist | NOT STARTED | AI Agent Quick Start | Update env var references and configuration guidance |

---

## Phase 4: Test Documentation

**Priority**: P2 — Medium
**Goal**: Ensure test documentation accurately reflects the test infrastructure

| ID | Task | Status | Section | Change |
|----|------|--------|---------|--------|
| R-021 | Add missing test markers to table | NOT STARTED | Pytest Markers | Add `requires_cassandra`, `api`, `generators` |
| R-022 | Expand test fixtures documentation | NOT STARTED | Key Test Fixtures | Add 6 missing fixtures, update `reset_singletons` |
| R-023 | Add missing test env vars | NOT STARTED | Test Environment Variables | Add `CASSANDRA_INTEGRATION_TEST`, `JUNIPER_DATA_E2E_TEST`, `REDIS_INTEGRATION_TEST` |
| R-024 | Update conftest.py demo mode note | NOT STARTED | Test Environment Variables | Update from `CASCOR_DEMO_MODE=1` to `JUNIPER_CANOPY_DEMO_MODE=1` |

---

## Phase 5: Documentation Organization

**Priority**: P2 — Medium
**Goal**: Fix documentation path references and structure

| ID | Task | Status | Section | Change |
|----|------|--------|---------|--------|
| R-025 | Fix root-level doc file locations | NOT STARTED | Root Directory Documentation | Move references from root to `docs/` |
| R-026 | Update notes/ subdirectory documentation | NOT STARTED | notes/ Subdirectory | Expand with actual subdirectory structure |
| R-027 | Add missing docs/ subdirectories | NOT STARTED | docs/ Subdirectory | Add `deployment/`, update testing refs |
| R-028 | Fix phase directory references | NOT STARTED | docs/ Subdirectory | Remove `docs/phase0-3/` reference; point to `notes/development/phase*/` and `notes/integration/phase_*/` |

---

## Phase 6: Completeness & Polish

**Priority**: P3 — Low
**Goal**: Address remaining gaps and modernize documentation

| ID | Task | Status | Section | Change |
|----|------|--------|---------|--------|
| R-029 | Update Docker section | NOT STARTED | Deployment | Remove "Future" label; document actual Docker support |
| R-030 | Expand GitHub Workflows section | NOT STARTED | CI/CD | Document all 4 workflow files |
| R-031 | Add MCP Server Availability section | NOT STARTED | New section | Document .mcp.json, Exa integration, notes/mcp/ guides |
| R-032 | Add scripts/ directory to structure | NOT STARTED | Directory Structure | Document 3 scripts |
| R-033 | Trim Recent Changes section | NOT STARTED | Recent Changes | Keep last 3-5 entries; reference CHANGELOG.md for history |
| R-034 | Verify conda environment name | NOT STARTED | Conda Environment | Cross-reference with parent CLAUDE.md |
| R-035 | Add Worktree Procedures section | NOT STARTED | New section | Reference notes/WORKTREE_SETUP_PROCEDURE.md and CLEANUP_V2 |

---

## Execution Summary

| Phase | Tasks | Priority | Estimated Effort |
|-------|-------|----------|-----------------|
| 1 | R-001 to R-003 | P0 CRITICAL | Small |
| 2 | R-004 to R-015 | P1 HIGH | Large |
| 3 | R-016 to R-020 | P1 HIGH | Large |
| 4 | R-021 to R-024 | P2 MEDIUM | Small |
| 5 | R-025 to R-028 | P2 MEDIUM | Small |
| 6 | R-029 to R-035 | P3 LOW | Medium |
| **Total** | **35 tasks** | | |

---

## Dependencies

- Phases 1-3 can execute in parallel (no cross-dependencies)
- Phase 4 depends on Phase 2 (env var prefix changes affect test env var references)
- Phase 5 is independent
- Phase 6 is independent

---

## Acceptance Criteria

All tasks complete when:

1. Every file path in AGENTS.md references an existing file
2. Every code example uses correct import paths and APIs
3. Every environment variable documented uses the current `JUNIPER_CANOPY_*` prefix
4. The directory structure tree matches actual project structure
5. All API endpoints in the application are documented
6. All test markers and fixtures are documented
7. All internal markdown links resolve correctly
