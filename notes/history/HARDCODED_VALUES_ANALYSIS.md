# Hardcoded Values Analysis — juniper-canopy

**Version**: 0.4.0
**Analysis Date**: 2026-04-08
**Analyst**: Claude Code (Automated Code Review)
**Status**: PLANNING ONLY — No source code modifications

---

## Executive Summary

The juniper-canopy codebase has **strong existing constants infrastructure** with 4 well-organized constants classes in `canopy_constants.py`, Pydantic BaseSettings in `settings.py`, and a separate `theme_constants.py` for UI styling. Of the values audited, **30+ are already covered** by existing constants. However, **21 operational values** remain hardcoded across middleware, service adapters, Redis client, training monitor, demo mode, and dashboard manager.

---

## 1. Existing Constants Infrastructure

| File | Classes/Sections | Coverage |
|------|-----------------|----------|
| `src/canopy_constants.py` | `TrainingConstants`, `DashboardConstants`, `ServerConstants`, `WebSocketConstants`, `JuniperDataConstants` | Excellent — 100+ constants with `typing.Final` |
| `src/settings.py` | `ServerSettings`, `WebSocketSettings`, `CascorDiscoverySettings`, `Settings` | Good — Pydantic BaseSettings with env overrides |
| `src/frontend/theme_constants.py` | `ThemeColors` | Good — centralized color tokens |
| `src/config_manager.py` | Legacy YAML-based config (deprecated) | Being phased out |

---

## 2. Hardcoded Values — NOT COVERED

### 2.1 Middleware (`src/middleware.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 63 | `10 * 1024 * 1024` | int | Max request body (10 MB) | `MAX_REQUEST_BODY_BYTES` |
| 15 | `("/dashboard",)` | tuple | Exempt path prefixes | `EXEMPT_PATH_PREFIXES` |
| 17-27 | Multiple paths | set | Exempt security paths | `EXEMPT_SECURITY_PATHS` |
| 33 | CSP header string | str | Content Security Policy | `DEFAULT_CSP_POLICY` |

**Target location**: `canopy_constants.py` → new `SecurityConstants` class

### 2.2 Service Discovery (`src/discovery.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 15 | `[8200]` | list | Default discovery ports | `DEFAULT_DISCOVERY_PORTS` |
| 16 | `"localhost"` | str | Default discovery host | `DEFAULT_DISCOVERY_HOST` |
| 17 | `2.0` | float | Default discovery timeout | `DEFAULT_DISCOVERY_TIMEOUT` |
| 23 | `"/v1/health/live"` | str | Health check endpoint | `HEALTH_LIVE_ENDPOINT` |

**Target location**: `canopy_constants.py` → `ServerConstants` (extend)

### 2.3 Service Adapters (`src/backend/cascor_service_adapter.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 143 | `"http://localhost:8200"` | str | Default CasCor service URL | `DEFAULT_CASCOR_SERVICE_URL` |
| 155 | `5` | int | Circuit breaker failure threshold | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| 155 | `60.0` | float | Circuit breaker recovery timeout | `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` |

**Target location**: `canopy_constants.py` → new `BackendConstants` class

### 2.4 Redis Client (`src/backend/redis_client.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 174 | `5.0` | float | Socket timeout | `REDIS_SOCKET_TIMEOUT` |
| 175 | `5.0` | float | Socket connect timeout | `REDIS_CONNECT_TIMEOUT` |

**Target location**: `canopy_constants.py` → `BackendConstants`

### 2.5 Training Monitor (`src/backend/training_monitor.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 404 | `10000` | int | Max metrics buffer size | `MAX_METRICS_BUFFER_SIZE` |

### 2.6 Dashboard Manager (`src/frontend/dashboard_manager.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 2567 | `2` | int | POST request timeout | `DASHBOARD_POST_TIMEOUT` |
| 2627 | `2` | int | Timeout threshold | `DASHBOARD_TIMEOUT_THRESHOLD` |
| 2834 | `10` | int | Long POST request timeout | `DASHBOARD_LONG_POST_TIMEOUT` |
| 2838 | `5` | int | GET request timeout | `DASHBOARD_GET_TIMEOUT` |

**Target location**: `canopy_constants.py` → `DashboardConstants` (extend)

### 2.7 Demo Mode (`src/demo_mode.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 1446, 1568 | `5.0` | float | Thread join timeout | `DEMO_THREAD_JOIN_TIMEOUT` |
| 1849 | `30` | int | Main loop sleep | `DEMO_MAIN_LOOP_SLEEP` |

### 2.8 Application (`src/main.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 365 | `'ws://localhost:8050/ws/training'` | str | WS URL example in docs | `WS_TRAINING_URL_EXAMPLE` |

### 2.9 CORS Origin (`src/frontend/components/dataset_plotter.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 305 | `"http://127.0.0.1:8050"` | str | CORS allowed origin | `CORS_LOCAL_ORIGIN` |

### 2.10 Cassandra Client (`src/backend/cassandra_client.py`)

| Line | Value | Type | Context | Proposed Constant Name |
|------|-------|------|---------|----------------------|
| 112 | `10` | int | Connect timeout | `CASSANDRA_CONNECT_TIMEOUT` |

---

## 3. Coverage Summary

| Category | Total | Covered | Not Covered | Priority |
|----------|-------|---------|-------------|----------|
| Training Constants | 20+ | 20+ | 0 | — |
| Dashboard Intervals | 5+ | 5+ | 0 | — |
| Server/WebSocket | 10+ | 10+ | 0 | — |
| JuniperData Config | 5+ | 5+ | 0 | — |
| Theme Colors | 30+ | 30+ | 0 | — |
| Middleware/Security | 4 | 0 | 4 | **HIGH** |
| Service Discovery | 4 | 0 | 4 | **HIGH** |
| Backend Adapters | 5 | 0 | 5 | **MEDIUM** |
| Dashboard Timeouts | 4 | 0 | 4 | **MEDIUM** |
| Demo Mode | 2 | 0 | 2 | **LOW** |
| Misc (CORS, Cassandra) | 2 | 0 | 2 | **LOW** |
| **TOTAL (uncovered)** | — | — | **21** | — |

---

## 4. Remediation Approach

### Recommended: Extend `canopy_constants.py` with New Classes

Add two new constants classes to the existing `canopy_constants.py`:

1. **`SecurityConstants`** — CSP policy, exempt paths, max request body, CORS origins
2. **`BackendConstants`** — Circuit breaker settings, Redis/Cassandra timeouts, CasCor default URL, metrics buffer size

Extend existing classes:

- **`DashboardConstants`** — Add HTTP request timeout constants
- **`ServerConstants`** — Add discovery defaults, health endpoint paths

**Strengths**:

- Follows the existing well-established pattern
- `typing.Final` annotations maintained
- Minimal new files
- Consistent with existing imports across the codebase

**Weaknesses**:

- `canopy_constants.py` grows by ~30 constants
- Some values overlap with `settings.py` defaults

**Guardrails**:

- Reference constants from `settings.py` field defaults where applicable
- Add validation test ensuring constants/settings alignment
- Document new classes in AGENTS.md

---

## 5. Files Requiring Modification

| File | Action | Replacements |
|------|--------|-------------|
| `src/canopy_constants.py` | **EXTEND** — add `SecurityConstants`, `BackendConstants` | +27 constants |
| `src/middleware.py` | **MODIFY** | 4 |
| `src/discovery.py` | **MODIFY** | 4 |
| `src/backend/cascor_service_adapter.py` | **MODIFY** | 3 |
| `src/backend/redis_client.py` | **MODIFY** | 2 |
| `src/backend/training_monitor.py` | **MODIFY** | 1 |
| `src/frontend/dashboard_manager.py` | **MODIFY** | 4 |
| `src/demo_mode.py` | **MODIFY** | 2 |
| `src/frontend/components/dataset_plotter.py` | **MODIFY** | 1 |
| `src/backend/cassandra_client.py` | **MODIFY** | 1 |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing constant imports | Very Low | Medium | Only adding new constants, not modifying existing |
| Dashboard behavior change | Very Low | Low | Constants preserve exact timeout values |
| Circuit breaker tuning disrupted | Very Low | Medium | Values match current hardcoded values exactly |
| Settings/constants value drift | Low | Medium | Add alignment validation test |
