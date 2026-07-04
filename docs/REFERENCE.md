# Reference

## Juniper Canopy Technical Reference Index

**Version:** 0.25.0
**Status:** Active
**Last Updated:** July 4, 2026
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

1. **Pydantic settings** (`JUNIPER_CANOPY_*` environment variables)
2. **YAML configuration** (`conf/app_config.yaml`) for legacy `ConfigManager` callers
3. **Constants module** (`src/canopy_constants.py`)

| Setting Category | Prefix | Examples |
|-----------------|--------|---------|
| Server | `JUNIPER_CANOPY_SERVER__*` | `JUNIPER_CANOPY_SERVER__HOST`, `JUNIPER_CANOPY_SERVER__PORT` |
| Training | `JUNIPER_CANOPY_TRAINING__*` | `JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT`, `JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT` |
| WebSocket | `JUNIPER_CANOPY_WEBSOCKET__*` | `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS`, `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS_PER_SESSION` |
| Demo Mode | `JUNIPER_CANOPY_DEMO_*` | `JUNIPER_CANOPY_DEMO_MODE`, `JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL` |
| Security | `JUNIPER_CANOPY_*` | `JUNIPER_CANOPY_FRONTING_AUTH_ATTESTED`, `JUNIPER_CANOPY_BROWSER_CONTROL_AUTH_ENABLED` |

See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for the complete environment variable reference.

---

## WebSocket Reference

Real-time communication channels for training updates and control.

| Channel | Path | Direction | Purpose |
|---------|------|-----------|---------|
| Training | `/ws/training` | Server -> Client | Metrics, state, topology updates |
| Control | `/ws/control` | Bidirectional | Start, stop, pause, resume, reset commands |

**Connection limits:** `/ws/training`, `/ws/control`, and legacy `/ws` all admit through
`WebSocketManager`. The stack-wide `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS` cap defaults to `50`;
per-IP and per-session caps default to `5` each. Over-cap connections close with code `1013`.
The per-IP cap is DoS dampening only and is not per-client identity behind NAT; the per-session cap
uses the anonymous `canopy_session` cookie for best-effort fairness.

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

**CI pipeline:** GitHub Actions with multi-version Python testing (3.12-3.14)

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

## Environment Variables Quick Reference

The most commonly used environment variables for juniper-canopy configuration. For the full list, see [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) and [DEVELOPER_CHEATSHEET.md](DEVELOPER_CHEATSHEET.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `JUNIPER_CANOPY_DEMO_MODE` | unset | Set `1` to enable demo mode (simulated training) |
| `JUNIPER_CANOPY_SERVER__HOST` | `127.0.0.1` | Server bind address; non-loopback requires `JUNIPER_CANOPY_FRONTING_AUTH_ATTESTED=true` |
| `JUNIPER_CANOPY_SERVER__PORT` | `8050` | Server port |
| `JUNIPER_CANOPY_SERVER__DEBUG` | `false` | Enable debug mode |
| `JUNIPER_CANOPY_FRONTING_AUTH_ATTESTED` | `false` | Operator attestation for non-loopback binds behind a fronting authenticating proxy |
| `JUNIPER_CANOPY_BACKEND_PATH` | `../juniper-cascor` | Path to CasCor backend |
| `JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT` | `1000000` | Default maximum training epochs |
| `JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT` | `0.01` | Default learning rate |
| `JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT` | `1000` | Default max hidden units |
| `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS` | `50` | Stack-wide WebSocket cap across all endpoints |
| `JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS_PER_SESSION` | `5` | Per-session WebSocket fairness cap keyed on `canopy_session` |
| `JUNIPER_CANOPY_WEBSOCKET__HEARTBEAT_INTERVAL` | `30` | Heartbeat interval (seconds) |
| `JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL` | `1.0` | Demo simulation step interval (seconds) |
| `JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS` | `1000` | Dashboard metrics refresh (ms) |
| `JUNIPER_CANOPY_LOG_FORMAT` | `text` | Set `json` for structured JSON logging |
| `JUNIPER_CANOPY_SENTRY_DSN` | unset | Sentry error tracking DSN |
| `JUNIPER_CANOPY_METRICS_ENABLED` | `false` | Enable Prometheus metrics (`juniper_canopy_*`) |

---

**Last Updated:** July 4, 2026
**Version:** 0.25.1
**Maintainer:** Paul Calnon
