# Reference

## Juniper Canopy Technical Reference Index

**Version:** 0.25.0
**Status:** Active
**Last Updated:** March 3, 2026
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Table of Contents

- [Overview](#overview)
- [API Reference](#api-reference)
- [Configuration Reference](#configuration-reference)
- [WebSocket Reference](#websocket-reference)
- [Testing Reference](#testing-reference)
- [CI/CD Reference](#cicd-reference)
- [CasCor Backend Reference](#cascor-backend-reference)
- [Demo Mode Reference](#demo-mode-reference)
- [Integration References](#integration-references)
- [Constants Reference](#constants-reference)

---

## Overview

This document serves as a central index for all technical reference documentation in juniper-canopy. Each section links to the detailed reference document for that subsystem.

For comprehensive usage guides, see the corresponding manuals linked from [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md).

---

## API Reference

Detailed REST API endpoint specifications and response schemas.

| Document | Purpose | Lines |
|----------|---------|-------|
| [API_REFERENCE.md](api/API_REFERENCE.md) | Complete endpoint specifications, request/response formats | ~2,090 |
| [API_SCHEMAS.md](api/API_SCHEMAS.md) | API response schema definitions | ~1,050 |

**Key endpoints:** `/api/metrics`, `/api/metrics/history`, `/api/network/topology`, `/api/decision_boundary`, `/api/dataset`

**Base URL:** `http://127.0.0.1:8050`

---

## Configuration Reference

Configuration follows a three-level hierarchy (highest to lowest priority):

1. **Environment variables** (`CASCOR_*`, `JUNIPER_CANOPY_*`)
2. **YAML configuration** (`conf/app_config.yaml`)
3. **Constants module** (`src/canopy_constants.py`)

| Setting Category | Prefix | Examples |
|-----------------|--------|---------|
| Server | `CASCOR_SERVER_*` | `CASCOR_SERVER_HOST`, `CASCOR_SERVER_PORT` |
| Training | `CASCOR_TRAINING_*` | `CASCOR_TRAINING_EPOCHS`, `CASCOR_TRAINING_LEARNING_RATE` |
| WebSocket | `CASCOR_WEBSOCKET_*` | `CASCOR_WEBSOCKET_MAX_CONNECTIONS` |
| Demo Mode | `CASCOR_DEMO_*` | `CASCOR_DEMO_MODE`, `CASCOR_DEMO_UPDATE_INTERVAL` |
| Frontend | `JUNIPER_CANOPY_*` | `JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS` |

See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for the complete environment variable reference.

---

## WebSocket Reference

Real-time communication channels for training updates and control.

| Channel | Path | Direction | Purpose |
|---------|------|-----------|---------|
| Training | `/ws/training` | Server -> Client | Metrics, state, topology updates |
| Control | `/ws/control` | Bidirectional | Start, stop, pause, resume, reset commands |

**Message format:**

```json
{
  "type": "state | metrics | topology | event | control_ack",
  "timestamp": 1700000000.123,
  "data": { }
}
```

See [API_REFERENCE.md](api/API_REFERENCE.md) for detailed WebSocket protocol documentation.

---

## Testing Reference

Comprehensive test framework configuration and reference.

| Document | Purpose | Lines |
|----------|---------|-------|
| [TESTING_REFERENCE.md](testing/TESTING_REFERENCE.md) | Markers, fixtures, pytest config | ~1,010 |
| [TESTING_ENVIRONMENT_SETUP.md](testing/TESTING_ENVIRONMENT_SETUP.md) | Test environment configuration | ~550 |
| [TESTING_REPORTS_COVERAGE.md](testing/TESTING_REPORTS_COVERAGE.md) | Coverage analysis and reporting | ~860 |
| [TEST_ENABLEMENT_QUICK_REFERENCE.md](testing/TEST_ENABLEMENT_QUICK_REFERENCE.md) | Quick marker/command cheat sheet | ~73 |
| [ADR_001_VALID_TEST_SKIPS.md](testing/ADR_001_VALID_TEST_SKIPS.md) | Architectural decision on valid test skips | ~84 |

**Key test commands:**

```bash
cd src
pytest tests/ -v                    # All tests
pytest -m unit -v                   # Unit tests only
pytest -m "not slow" -v             # Exclude slow tests
pytest tests/ --cov=. --cov-report=html  # Coverage report
```

---

## CI/CD Reference

Pipeline configuration, hooks, and workflow reference.

| Document | Purpose | Lines |
|----------|---------|-------|
| [CICD_REFERENCE.md](ci_cd/CICD_REFERENCE.md) | Jobs, hooks, environment variables | ~1,060 |
| [CICD_ENVIRONMENT_SETUP.md](ci_cd/CICD_ENVIRONMENT_SETUP.md) | CI/CD environment configuration | ~484 |

**Pre-commit hooks:** black, isort, flake8, mypy, bandit, yamllint

**CI pipeline:** GitHub Actions with multi-version Python testing (3.11-3.14)

---

## CasCor Backend Reference

Technical reference for CasCor neural network backend integration.

| Document | Purpose | Lines |
|----------|---------|-------|
| [CASCOR_BACKEND_REFERENCE.md](cascor/CASCOR_BACKEND_REFERENCE.md) | Integration API, configuration, architecture | ~836 |
| [CONSTANTS_GUIDE.md](cascor/CONSTANTS_GUIDE.md) | Constants management and naming conventions | ~789 |

**Integration modes:** Demo mode (simulated) and real backend (CasCor connection)

---

## Demo Mode Reference

Technical reference for the demo mode simulation system.

| Document | Purpose | Lines |
|----------|---------|-------|
| [DEMO_MODE_REFERENCE.md](demo/DEMO_MODE_REFERENCE.md) | Demo mode technical reference | ~895 |
| [DEMO_MODE_ENVIRONMENT_SETUP.md](demo/DEMO_MODE_ENVIRONMENT_SETUP.md) | Demo environment configuration | ~340 |

**Activation:** `CASCOR_DEMO_MODE=1` (set automatically by `./demo` script)

---

## Integration References

Planned integration documentation for future subsystems.

| Document | Purpose | Status |
|----------|---------|--------|
| [REDIS_INTEGRATION_REFERENCE.md](redis/REDIS_INTEGRATION_REFERENCE.md) | Redis cache integration | Planned |
| [CASSANDRA_INTEGRATION_REFERENCE.md](cassandra/CASSANDRA_INTEGRATION_REFERENCE.md) | Cassandra persistence integration | Planned |
| [KUBERNETES_DEPLOYMENT_PLAN.md](deployment/KUBERNETES_DEPLOYMENT_PLAN.md) | Kubernetes deployment architecture | Planning |

---

## Constants Reference

Application constants are centralized in `src/canopy_constants.py`:

| Class | Purpose |
|-------|---------|
| `TrainingConstants` | Training parameters (epochs, learning rates, hidden units) |
| `DashboardConstants` | UI behavior (update intervals, timeouts, data limits) |
| `ServerConstants` | Server configuration (host, port, WebSocket paths) |

See [CONSTANTS_GUIDE.md](cascor/CONSTANTS_GUIDE.md) for the complete constants management guide.

---

**Last Updated:** March 3, 2026
**Version:** 0.25.0
**Maintainer:** Paul Calnon
