<div align="right" width="150px" height="150px" align="right" valign="top"> <img src="src/assets/Juniper_Logo_150px.png" alt="Juniper" align="right" valign="top" width="150px" /></div>
<br /> <br /> <br /> <br />

# Juniper: Dynamic Neural Network Research Platform

Juniper is an AI/ML research platform for investigating dynamic neural network architectures and novel learning paradigms.  The project emphasizes ground-up implementations from primary literature, enabling a more transparent exploration of fundamental algorithms.

## Juniper Canopy

`juniper-canopy` is the **real-time monitoring dashboard** of the Juniper platform.
Built on Dash and FastAPI, it consumes both the REST surface and the WebSocket training-stream of `juniper-cascor` to render live training dynamics, network topology, decision boundaries, and dataset previews as a Cascade-Correlation network grows.
It additionally exposes a WebSocket control surface through which a researcher can pause, resume, and step a running training run from the dashboard itself.
Canopy is the operator-facing surface of the platform: where the other components implement the algorithms and provide the data, Canopy is where a researcher inspects and steers the experiment as it runs.

## Distribution

`juniper-canopy` is published on PyPI as **[`juniper-canopy`](https://pypi.org/project/juniper-canopy/)**.
The package is also surfaced through the platform meta-distribution
**[`juniper-ml`](https://pypi.org/project/juniper-ml/)**, which installs
the full client stack via `pip install juniper-ml[all]`.

```bash
pip install juniper-canopy
```

## Ecosystem Compatibility

This service is part of the [Juniper](https://github.com/pcalnon/juniper-ml) ecosystem.
Verified compatible versions:

| juniper-data | juniper-cascor | juniper-canopy | data-client | cascor-client | cascor-worker |
|--------------|----------------|----------------|-------------|---------------|---------------|
| 0.6.x        | 0.4.x          | 0.4.x          | >=0.4.1     | >=0.4.0       | >=0.3.0       |

For full-stack Docker deployment and integration tests, see [`juniper-deploy`](https://github.com/pcalnon/juniper-deploy).

## Architecture

`juniper-canopy` is the **monitoring dashboard** of the Juniper ecosystem. It depends on both `juniper-cascor` (for live training data over REST + WebSocket) and `juniper-data` (for dataset previews via REST).

```text
┌─────────────────────┐     REST+WS      ┌──────────────────────┐
│   JuniperCanopy     │ ◄──────────────► │    JuniperCascor     │
│   Dashboard  ◄─here │                  │    Training Svc      │
│   Port 8050         │                  │    Port 8200         │
└──────────┬──────────┘                  └──────────┬───────────┘
           │ REST                                   │ REST
           ▼                                        ▼
┌──────────────────────────────────────────────────────────────┐
│                      JuniperData                             │
│                   Dataset Service  ·  Port 8100              │
└──────────────────────────────────────────────────────────────┘
```

**Modes**: *service mode* (live CasCor backend via `JUNIPER_CANOPY_CASCOR_SERVICE_URL`, with legacy fallback `CASCOR_SERVICE_URL`) or *demo mode* (`JUNIPER_CANOPY_DEMO_MODE=1`, no backend required).

## Related Services

| Service | Relationship | Notes |
|---------|-------------|-------|
| [juniper-cascor](https://github.com/pcalnon/juniper-cascor) | Canopy monitors CasCor training | Set `JUNIPER_CANOPY_CASCOR_SERVICE_URL` (or legacy `CASCOR_SERVICE_URL`) to activate service mode |
| [juniper-data](https://github.com/pcalnon/juniper-data) | Canopy fetches datasets for visualization | Set `JUNIPER_DATA_URL` |
| [juniper-cascor-client](https://github.com/pcalnon/juniper-cascor-client) | REST + WebSocket client used internally by Canopy | `pip install juniper-cascor-client` |

## Service Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JUNIPER_CANOPY_CASCOR_SERVICE_URL` | Yes\* | — | `juniper-cascor` URL — activates service mode |
| `JUNIPER_DATA_URL` | No | `http://localhost:8100` | `juniper-data` URL (optional in demo mode due to local fallback) |
| `JUNIPER_CANOPY_DEMO_MODE` | No | `false` (`1` in Docker image) | Set to `1` to run without a backend |
| `JUNIPER_CANOPY_SERVER__HOST` | No | `127.0.0.1` | Server bind address |
| `JUNIPER_CANOPY_SERVER__PORT` | No | `8050` | Server port |
| `CASCOR_SERVICE_URL` | No | — | Legacy fallback for `JUNIPER_CANOPY_CASCOR_SERVICE_URL` |
| `CASCOR_DEMO_MODE` | No | — | Legacy fallback for `JUNIPER_CANOPY_DEMO_MODE` |

\* Required for service mode. Omit to fall back to demo mode.

Variables are sourced from `src/settings.py` (Pydantic `BaseSettings`, `env_prefix="JUNIPER_CANOPY_"`).

## Docker Deployment

```bash
# Full stack (recommended) — see juniper-deploy:
git clone https://github.com/pcalnon/juniper-deploy.git  # (private repository)
cd juniper-deploy && docker compose up --build

# Standalone (demo mode by default in Dockerfile):
docker build -t juniper-canopy:latest .
docker run --rm -p 8050:8050 juniper-canopy:latest

# Standalone (service mode with external CasCor):
docker run --rm -p 8050:8050 \
  -e JUNIPER_CANOPY_DEMO_MODE=0 \
  -e JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://host.docker.internal:8200 \
  -e JUNIPER_DATA_URL=http://host.docker.internal:8100 \
  juniper-canopy:latest
```

In demo mode, dataset generation first attempts to connect to a running `juniper-data` service and falls back to local spiral-dataset generation if the dataset service is unavailable; the fallback is logged at WARNING level.

## Dependency Lockfile

The `requirements.lock` file pins exact dependency versions for reproducible Docker builds. The `pyproject.toml` retains flexible `>=` ranges for local development.

Regenerate after changing dependencies in `pyproject.toml`:

```bash
uv pip compile pyproject.toml --extra juniper-data --extra juniper-cascor --extra observability -o requirements.lock
```

The `observability` extra includes optional runtime integrations used by `src/observability.py` (`prometheus-client`, `sentry-sdk`). All dependencies, including `juniper-data-client` and `juniper-cascor-client`, are resolved from PyPI.

## Active Research Components

Canopy contributes four operator-facing research components to the Juniper platform:
a **live network-topology renderer** that visualises Cascade-Correlation network growth as units are recruited;
a **dataset previewer** that surfaces the current training and test sets alongside their named-version metadata from `juniper-data`;
a **training-history viewer** that streams loss, accuracy, and per-epoch metrics over the WebSocket training stream;
and a **WebSocket control surface** for pausing, resuming, and stepping a running training run from the dashboard (Phase D §S10, shipped 2026-04-14).

## Quick Start Guide

### Prerequisites

- Python ≥ 3.11
- Conda environment `JuniperCanopy` (rebuilt envs may be named `JuniperCanopy1` per `notes/JUNIPER_CONDA_ENV_REBUILD_PROCEDURE.md` in the parent ecosystem documentation)
- Git
- For service mode: a running `juniper-cascor` instance on `http://<host>:8200`; optionally a running `juniper-data` instance on `http://<host>:8100`

### Installation

```bash
git clone https://github.com/pcalnon/juniper-canopy.git
cd juniper-canopy
conda activate JuniperCanopy
pip install -e ".[dev]"
```

The PyPI release of the dashboard package is installable via `pip install juniper-canopy`; the editable-clone form above is the standard for active development.

### Verification — Demo Mode

Demo mode runs without the CasCor backend, simulating training data for development and testing:

```bash
./demo
```

Expected output:

```text
INFO:     Uvicorn running on http://0.0.0.0:8050 (Press CTRL+C to quit)
Dash is running on http://127.0.0.1:8050/
```

Open the dashboard at `http://localhost:8050/dashboard/` and confirm the **Training Metrics**, **Network Topology**, **Decision Boundary**, and **Dataset** tabs render.

Health and metrics endpoints:

```bash
curl http://localhost:8050/v1/health
curl http://localhost:8050/api/metrics
curl http://localhost:8050/api/topology
```

### Verification — Service Mode

Service mode connects the dashboard to a live `juniper-cascor` backend:

```bash
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://<cascor-host>:8200
export JUNIPER_DATA_URL=http://<data-host>:8100
unset JUNIPER_CANOPY_DEMO_MODE   # ensure demo mode is off
./try
```

A successful service-mode start logs `Control stream supervisor connected` once the WebSocket handshake completes against `juniper-cascor`. Absence of that log line typically indicates an authentication or URL configuration issue rather than a CasCor-side problem; cross-check `JUNIPER_CANOPY_CASCOR_SERVICE_URL` first.

### Next Steps

- [`docs/QUICK_START.md`](docs/QUICK_START.md) — complete installation and verification guide
- [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) — comprehensive usage guide
- [`docs/cascor/CASCOR_BACKEND_MANUAL.md`](docs/cascor/CASCOR_BACKEND_MANUAL.md) — complete CasCor integration guide
- [`juniper-deploy`](https://github.com/pcalnon/juniper-deploy) — Docker Compose orchestration for the full-stack platform
- [`juniper-ml`](https://pypi.org/project/juniper-ml/) — platform meta-package on PyPI

## Research Philosophy

The Juniper platform exists to study learning algorithms whose network architecture is not fixed in advance.
Its initial anchor is the Cascade-Correlation algorithm of Fahlman and Lebiere (1990), implemented from the primary literature without recourse to higher-level abstractions that elide the algorithm's operational detail.
The organising commitment is that algorithm implementations remain inspectable at the level at which they were originally specified: candidate units, correlation objectives, weight-freezing semantics, and the structural events that grow the network are first-class artifacts of the codebase rather than internal details of a library wrapper.
This permits comparative work — across algorithms, datasets, and hyperparameter regimes — to be conducted on a known and reproducible substrate.

The current platform comprises a Cascade-Correlation training service exposing a REST and WebSocket interface, a dataset-generation service with a named-version registry that includes the ARC-AGI families, a real-time monitoring dashboard for inspecting training dynamics as they occur, and a distributed worker that parallelises candidate-unit training across hosts.
Near-term work extends the architectural-growth catalogue beyond Cascade-Correlation, introduces multi-network orchestration for comparative experiments at the level of network populations rather than individual runs, and tightens the dataset–training–monitoring loop into a reproducible research workbench.
The longer-term direction is the systematic empirical study of constructive and architecture-growing learning algorithms, with first-class infrastructure for the ablation, comparison, and replication that such a study requires.

## Documentation

### Documentation Overview

| Document | Purpose |
|----------|---------|
| [`docs/DOCUMENTATION_OVERVIEW.md`](docs/DOCUMENTATION_OVERVIEW.md) | Navigation index for all `juniper-canopy` documentation |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history and release notes |
| [`docs/cascor/CONSTANTS_GUIDE.md`](docs/cascor/CONSTANTS_GUIDE.md) | Application constants reference |

### Installation and Configuration

| Document | Purpose |
|----------|---------|
| [`docs/QUICK_START.md`](docs/QUICK_START.md) | Get running in five minutes |
| [`docs/ENVIRONMENT_SETUP.md`](docs/ENVIRONMENT_SETUP.md) | Complete environment configuration |
| [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) | Comprehensive usage guide |

### API Documentation

| Document | Purpose |
|----------|---------|
| [`docs/api/API_REFERENCE.md`](docs/api/API_REFERENCE.md) | Complete REST API and WebSocket documentation |
| [`docs/api/API_SCHEMAS.md`](docs/api/API_SCHEMAS.md) | Request/response JSON schemas |

### CasCor Backend Documentation

| Document | Purpose |
|----------|---------|
| [`docs/cascor/CASCOR_BACKEND_QUICK_START.md`](docs/cascor/CASCOR_BACKEND_QUICK_START.md) | Connect to CasCor in five minutes |
| [`docs/cascor/CASCOR_BACKEND_MANUAL.md`](docs/cascor/CASCOR_BACKEND_MANUAL.md) | Complete integration guide |
| [`docs/cascor/CASCOR_BACKEND_REFERENCE.md`](docs/cascor/CASCOR_BACKEND_REFERENCE.md) | Technical API reference |

### CI/CD Documentation

| Document | Purpose |
|----------|---------|
| [`docs/ci_cd/CICD_QUICK_START.md`](docs/ci_cd/CICD_QUICK_START.md) | Get CI/CD running in five minutes |
| [`docs/ci_cd/CICD_ENVIRONMENT_SETUP.md`](docs/ci_cd/CICD_ENVIRONMENT_SETUP.md) | Complete CI/CD environment configuration |
| [`docs/ci_cd/CICD_MANUAL.md`](docs/ci_cd/CICD_MANUAL.md) | Comprehensive CI/CD usage guide |
| [`docs/ci_cd/CICD_REFERENCE.md`](docs/ci_cd/CICD_REFERENCE.md) | CI/CD technical reference |

The CI/CD docs include operational guidance for the `juniper-check-doc-links` markdown link validator (formerly the in-repo `scripts/check_doc_links.py`), including cross-repo validation modes (`skip`, `warn`, `check`) and documentation-link gate troubleshooting.

### Demo Mode Documentation

| Document | Purpose |
|----------|---------|
| [`docs/demo/DEMO_MODE_QUICK_START.md`](docs/demo/DEMO_MODE_QUICK_START.md) | Start demo mode in five minutes |
| [`docs/demo/DEMO_MODE_ENVIRONMENT_SETUP.md`](docs/demo/DEMO_MODE_ENVIRONMENT_SETUP.md) | Demo mode configuration |
| [`docs/demo/DEMO_MODE_MANUAL.md`](docs/demo/DEMO_MODE_MANUAL.md) | Complete demo mode guide |
| [`docs/demo/DEMO_MODE_REFERENCE.md`](docs/demo/DEMO_MODE_REFERENCE.md) | Demo mode technical reference |

### Testing Documentation

| Document | Purpose |
|----------|---------|
| [`docs/testing/TESTING_QUICK_START.md`](docs/testing/TESTING_QUICK_START.md) | Run tests in five minutes |
| [`docs/testing/TESTING_ENVIRONMENT_SETUP.md`](docs/testing/TESTING_ENVIRONMENT_SETUP.md) | Test environment configuration |
| [`docs/testing/TESTING_MANUAL.md`](docs/testing/TESTING_MANUAL.md) | Comprehensive testing guide |
| [`docs/testing/TESTING_REFERENCE.md`](docs/testing/TESTING_REFERENCE.md) | Testing technical reference |
| [`docs/testing/TESTING_REPORTS_COVERAGE.md`](docs/testing/TESTING_REPORTS_COVERAGE.md) | Coverage analysis and reports |
| [`docs/testing/TESTING_ANALYSIS_REPORT.md`](docs/testing/TESTING_ANALYSIS_REPORT.md) | Test suite analysis |
| [`docs/testing/TEST_ENABLEMENT_QUICK_REFERENCE.md`](docs/testing/TEST_ENABLEMENT_QUICK_REFERENCE.md) | Quick test enablement guide |
| [`docs/testing/SELECTIVE_TEST_GUIDE.md`](docs/testing/SELECTIVE_TEST_GUIDE.md) | Run specific test subsets |
| [`docs/testing/SELECTIVE_TEST_ENABLEMENT_SUMMARY.md`](docs/testing/SELECTIVE_TEST_ENABLEMENT_SUMMARY.md) | Test enablement overview |

## License

MIT License — see [`LICENSE`](LICENSE) for details.
