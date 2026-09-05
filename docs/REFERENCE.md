# Reference

## Juniper Canopy Technical Reference Index

**Version:** 0.25.2
**Status:** Active
**Last Updated:** September 4, 2026
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Table of Contents

- [Overview](#overview)
- [Topology Node Selection](#topology-node-selection)
- [AGENTS Reference](#agents-reference)
- [Hierarchy Depth Filter](#hierarchy-depth-filter)
- [Plotly PNG Export / CSP](#plotly-png-export--csp)
- [API Reference](#api-reference)
- [Configuration Reference](#configuration-reference)
- [WebSocket Reference](#websocket-reference)
- [Testing Reference](#testing-reference)
- [Event-loop I/O discipline (X7)](#event-loop-io-discipline-x7)
- [Cascor status cache (X7 slice 1c)](#cascor-status-cache-x7-slice-1c)
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

## Topology Node Selection

Click / box / lasso highlight on the Network Topology tab. The panel's "click elsewhere to deselect" sentence is false on `main` (plotly emits `plotly_click` only on a point hit). Clicking the selected node again *does* clear. `-selected-nodes` is an Input of `update_network_graph`; an unguarded `[]` write costs a 1.5–31 s rebuild. canopy#573 (not yet on `main`) adds a Clear button and returns `dash.no_update` when there is nothing to clear.

| Document | Purpose |
|----------|---------|
| [AGENTS_REFERENCE.md § Topology Node Selection](AGENTS_REFERENCE.md#topology-node-selection-f-canopy-046) | Developer contract: F-044 `customdata` fallback, F-045 label-derived layer, F-046 empty-canvas no-event, store-write cost, incoming #573 |
| [USER_MANUAL.md § Network Topology Tab](USER_MANUAL.md#network-topology-tab) | Operator gestures and the false "elsewhere" hint |

---

## AGENTS Reference

Reference material relocated **verbatim** out of `AGENTS.md` under the shared-session-memory plan (juniper-ml plan §P5 step e), so it is read on demand rather than loaded into every session. Nothing was rewritten; each relocated section carries a provenance line naming where it came from.

| Document | Purpose | Lines |
|----------|---------|-------|
| [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md) | Layered architecture and callback topology, the three-level configuration hierarchy, and the REST/WebSocket contract | ~580 |

The same cut sent documentation-about-documentation to [DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md) instead, which is the file whose subject that already is.

**Hazards were deliberately not relocated.** Directives whose non-application destroys work stay resident in [`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate), because a pointer only helps an agent that already knows to look.

---

## Hierarchy Depth Filter

CAN-020 view filter on the Network Topology tab. `_apply_hierarchy_filter` is the oracle (`0` / `None` / `>= N` → `"all"`). F-CANOPY-042 is the label-wiring defect (slider value was State, not Input; rest-state `0` rendered `"0 of N"`). Repair lands in canopy#570 as a dedicated clientside callback — do not merge it back into the bounds-sync callback (circular dependency).

| Document | Purpose |
|----------|---------|
| [AGENTS_REFERENCE.md § Hierarchy Depth Filter](AGENTS_REFERENCE.md#hierarchy-depth-filter-can-020) | Developer contract: filter arms, label split, tests, pitfalls |
| [USER_MANUAL.md § Network Topology Tab](USER_MANUAL.md#network-topology-tab) | Operator: slider, `"all"` vs `"K of N"`, rest-state `0` |
| [DEVELOPER_CHEATSHEET.md § 6](DEVELOPER_CHEATSHEET.md#6-change-the-depth-filter-label-or-filter) | Short procedure + troubleshooting row |

---

## Plotly PNG Export / CSP

The Topology modebar camera is a Plotly PNG export. It rasterises SVG →
Blob → `<img>` → canvas, so `img-src` must allow `blob:` **and** `data:`
(Bootstrap icons). `blob:` belongs on `img-src` only — not `script-src`
or `default-src`. There is no CSP environment variable; the shipped
string is `SecurityConstants.DEFAULT_CSP_POLICY`, aliased as
`middleware._DEFAULT_CSP`.

| Document | Purpose |
|----------|---------|
| [AGENTS_REFERENCE.md § Plotly PNG Export](AGENTS_REFERENCE.md#plotly-png-export-f-canopy-047) | Operator runbook (F-CANOPY-047) |
| [USER_MANUAL.md troubleshooting #6](USER_MANUAL.md#6-modebar-camera-does-nothing-no-png-file) | Silent-camera symptom |
| [`test_csp_plotly_image_export.py`](../src/tests/regression/test_csp_plotly_image_export.py) | Pins `blob:` on `img-src` only |
| [`test_csp_bootstrap_cdn.py`](../src/tests/regression/test_csp_bootstrap_cdn.py) | Pins `data:` + Bootstrap CDN |

```bash
cd src
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v
```

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
| Security | `JUNIPER_CANOPY_*` | `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED`, `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`, `JUNIPER_CANOPY_BROWSER_CONTROL_AUTH_ENABLED` |

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

## Event-loop I/O discipline (X7)

Canopy is a single-worker uvicorn. Synchronous `requests` I/O inside `async def` stalls
every route, including `/v1/health/live`. Slice 1b (`#566`) bounds the cascor client
budget; slice 1a (`#567`) moves remaining calls off the loop.

| Surface | Purpose |
| --- | --- |
| [AGENTS_REFERENCE.md § Event-loop I/O discipline](AGENTS_REFERENCE.md#event-loop-io-discipline-x7) | Operator runbook: idiom, gate, T-A2/T-A3/T-A4, callgraph, pitfalls |
| [`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate) | Resident one-line hazard |
| `src/tests/regression/test_x7_client_budget.py` | Slice 1b — T-B1 / T-B2 (on `main`) |
| `src/tests/regression/test_x7_off_loop_discipline.py` | Slice 1a structural gate (`main.py` only) |
| `src/tests/regression/test_x7_loop_responsiveness.py` | Slice 1a behavioural tests |
| `util/ad-hoc/2026-09-04_async_blocking_callgraph.py` | Adapter-wide census (instrument, not a gate) |

```bash
cd src && pytest tests/regression/test_x7_client_budget.py -v
```

---

## Cascor status cache (X7 slice 1c)

Incoming with `#578`. One background task polls cascor; `/api/status` and the status bar
serve its **class** (`ok` / `unreachable` / `indeterminate`), not a raw payload. That is
what keeps a half-dead 200 from rendering as a healthy **"Stopped"**.

| Document | Purpose |
|----------|---------|
| [AGENTS_REFERENCE.md § Cascor status cache](AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c) | Operator runbook: intervals, classifier, dedicated breaker, C6 / C7 / C9, T-C1–T-C4 |

# Lands with #578 — do not markdown-link the file until it exists on main
cd src && pytest tests/regression/test_x7_status_cache.py -v

Distinct from the 1a / 1b off-loop runbook (docs `#568`).

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

**Activation:** `JUNIPER_CANOPY_DEMO_MODE=1` (set automatically by the `./demo` script; the legacy `CASCOR_DEMO_MODE` alias still works, with a deprecation warning)

---

## Integration References

Documentation for the shipped Redis and Cassandra monitoring tabs, and for the planned Kubernetes
deployment.

| Document | Purpose | Status |
|----------|---------|--------|
| [REDIS_INTEGRATION_REFERENCE.md](redis/REDIS_INTEGRATION_REFERENCE.md) | Redis cache integration | Shipped — read-only **Redis** tab backed by `GET /api/v1/redis/status` and `GET /api/v1/redis/metrics` |
| [CASSANDRA_INTEGRATION_REFERENCE.md](cassandra/CASSANDRA_INTEGRATION_REFERENCE.md) | Cassandra persistence integration | Shipped — read-only **Cassandra** tab backed by `GET /api/v1/cassandra/status` and `GET /api/v1/cassandra/metrics` |
| [KUBERNETES_DEPLOYMENT_PLAN.md](deployment/KUBERNETES_DEPLOYMENT_PLAN.md) | Kubernetes deployment architecture | Planning |

---

## Constants Reference

Application constants are centralized in `src/canopy_constants.py`:

| Class | Purpose |
|-------|---------|
| `TrainingConstants` | Training parameters (epochs, learning rates, hidden units) |
| `DashboardConstants` | UI behavior (update intervals, timeouts, data limits) |
| `ServerConstants` | Server configuration (host, port, WebSocket paths) |
| `SecurityConstants` | HTTP headers and `DEFAULT_CSP_POLICY` (`img-src 'self' data: blob:`) |

See [CONSTANTS_GUIDE.md](cascor/CONSTANTS_GUIDE.md) for the complete constants management guide.

---

## Environment Variables Quick Reference

The most commonly used environment variables for juniper-canopy configuration. For the full list, see [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) and [DEVELOPER_CHEATSHEET.md](DEVELOPER_CHEATSHEET.md).

| Variable | Default | Description |
|----------|---------|-------------|
| `JUNIPER_CANOPY_DEMO_MODE` | unset | Set `1` to enable demo mode (simulated training) |
| `JUNIPER_CANOPY_SERVER__HOST` | `127.0.0.1` | Server bind address; non-loopback requires `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` or `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true` |
| `JUNIPER_CANOPY_SERVER__PORT` | `8050` | Server port |
| `JUNIPER_CANOPY_SERVER__DEBUG` | `false` | Enable debug mode |
| `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` | `false` | Operator attestation: non-loopback bind is reachable only via a loopback-only host publish (containerized default) |
| `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED` | `false` | Operator attestation: a fronting authenticating reverse proxy terminates access (Phase 4) |
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

**Last Updated:** September 4, 2026
**Version:** 0.25.2
**Maintainer:** Paul Calnon
