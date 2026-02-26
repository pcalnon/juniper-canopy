<div align="right" width="150px" height="150px" align="right" valign="top"> <img src="src/assets/Juniper_Logo_150px.png" alt="Juniper" align="right" valign="top" width="150px" /></div>
<br /> <br /> <br /> <br />

# Juniper: Dynamic Neural Network Research Platform

Juniper is an AI/ML research platform for investigating dynamic neural network architectures and novel learning paradigms.  The project emphasizes ground-up implementations from primary literature, enabling a more transparent exploration of fundamental algorithms.

## Ecosystem Compatibility

This service is part of the [Juniper](https://github.com/pcalnon/juniper-ml) ecosystem.
Verified compatible versions:

| juniper-data | juniper-cascor | juniper-canopy | data-client | cascor-client | cascor-worker |
|---|---|---|---|---|---|
| 0.4.x | 0.3.x | 0.2.x | >=0.3.1 | >=0.1.0 | >=0.1.0 |

For full-stack Docker deployment and integration tests, see [juniper-deploy](https://github.com/pcalnon/juniper-deploy).

## Architecture

JuniperCanopy is the **monitoring dashboard** of the Juniper ecosystem. It depends on both JuniperData and JuniperCascor to display real-time training data.

```text
┌─────────────────────┐     REST+WS      ┌──────────────────────┐
│   JuniperCanopy     │ ◄──────────────► │    JuniperCascor     │
│   Dashboard  ◄─here │                  │    Training Svc      │
│   Port 8050         │                  │    Port 8200         │
└──────────┬──────────┘                  └──────────┬───────────┘
           │ REST                                    │ REST
           ▼                                         ▼
┌──────────────────────────────────────────────────────────────┐
│                      JuniperData                              │
│                   Dataset Service  ·  Port 8100               │
└──────────────────────────────────────────────────────────────┘
```

**Modes**: *Service mode* (live CasCor backend via `CASCOR_SERVICE_URL`) or *Demo mode* (`CASCOR_DEMO_MODE=1`, no backend required).

## Related Services

| Service | Relationship | Notes |
|---------|-------------|-------|
| [juniper-cascor](https://github.com/pcalnon/juniper-cascor) | Canopy monitors CasCor training | Set `CASCOR_SERVICE_URL` to activate service mode |
| [juniper-data](https://github.com/pcalnon/juniper-data) | Canopy fetches datasets for visualization | Set `JUNIPER_DATA_URL` |
| [juniper-cascor-client](https://github.com/pcalnon/juniper-cascor-client) | REST+WS client used internally by Canopy | `pip install juniper-cascor-client` |

### Service Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CASCOR_SERVICE_URL` | Yes\* | — | JuniperCascor URL — activates service mode |
| `JUNIPER_DATA_URL` | No | `http://localhost:8100` | JuniperData URL |
| `CASCOR_DEMO_MODE` | No | — | Set to `1` to run without a backend |
| `CANOPY_HOST` | No | `0.0.0.0` | Listen address |
| `CANOPY_PORT` | No | `8050` | Service port |

\* Required for service mode. Omit to fall back to demo mode.

### Docker Deployment

```bash
# Full stack (recommended):
git clone https://github.com/pcalnon/juniper-deploy.git
cd juniper-deploy && docker compose up --build

# Standalone (service mode):
docker build -t juniper-canopy:latest .
docker run -p 8050:8050 \
  -e CASCOR_SERVICE_URL=http://host.docker.internal:8200 \
  -e JUNIPER_DATA_URL=http://host.docker.internal:8100 \
  juniper-canopy:latest
```

## Active Research Components

**juniper_cascor**:  Cascade Correlation Neural Network

- Reference implementation from foundational research (Fahlman & Lebiere, 1990)
- Designed for flexibility, modularity, and scalability
- Enables investigation of constructive learning algorithms

**juniper_canopy**:  Interactive Research Interface

- Research-driven monitoring and visualization environment
- Delivers novel observations through real-time network introspection
- Transforms metrics into insights, accelerating experimental iteration

## Research Philosophy

Juniper prioritizes **transparency over convenience** and **understanding over abstraction**.  By implementing algorithms from first principles, the platform provides increased visibility into network behavior, enabling a more rigorous and more controlled investigation of learning dynamics and architectural innovations.

---

## Quick Start Guide

### Get Juniper Canopy running in 5 minutes

**Version:** 0.25.0  
**Status:** ✅ Production Ready

### Prerequisites

- **Python 3.11 or higher** installed
- **Conda/Mamba** (Miniforge3 or Miniconda)
- **Git** for cloning the repository

### Quick Start (Demo Mode)

Demo mode runs without the CasCor backend, simulating training data for development and testing.

```bash
# Clone the repository
git clone https://github.com/pcalnon/juniper-canopy.git
cd juniper-canopy

# Activate environment
conda activate JuniperCanopy

# Launch demo mode
./demo
```

**Expected output:**

```bash
INFO:     Uvicorn running on http://0.0.0.0:8050 (Press CTRL+C to quit)
Dash is running on http://127.0.0.1:8050/
```

**Open Dashboard:** Navigate to `http://localhost:8050/dashboard/`

You should see:

- ✅ **Training Metrics** tab with live loss/accuracy plots
- ✅ **Network Topology** tab with network visualization
- ✅ **Decision Boundary** tab with boundary plot
- ✅ **Dataset** tab with data points

### Verify Installation

```bash
# Health check
curl http://localhost:8050/health

# Get current metrics
curl http://localhost:8050/api/metrics

# Get network topology
curl http://localhost:8050/api/topology
```

### Production Mode

Connect to the real CasCor backend:

```bash
# Set backend path
export CASCOR_BACKEND_PATH=/path/to/cascor

# Disable demo mode
unset CASCOR_DEMO_MODE

# Launch
./try
```

For complete setup instructions, see [docs/QUICK_START.md](docs/QUICK_START.md).

---

## Documentation

### Documentation Overview

- [Documentation Overview](docs/DOCUMENTATION_OVERVIEW.md) - Complete navigation guide
- [README.md](README.md) - This file
- [CHANGELOG.md](CHANGELOG.md) - Version history and release notes
- [Constants Guide](docs/cascor/CONSTANTS_GUIDE.md) - Application constants reference

### Install and Configuration

- [Quick Start Guide](docs/QUICK_START.md) - Get running in 5 minutes
- [Environment Setup Guide](docs/ENVIRONMENT_SETUP.md) - Complete environment configuration
- [User Manual](docs/USER_MANUAL.md) - Comprehensive usage guide

### API Documentation

- [API Reference](docs/api/API_REFERENCE.md) - Complete REST API and WebSocket documentation
- [API Schemas](docs/api/API_SCHEMAS.md) - Request/response JSON schemas

### Cascor Backend Documentation

- [CasCor Backend Quick Start](docs/cascor/CASCOR_BACKEND_QUICK_START.md) - Connect to CasCor in 5 minutes
- [CasCor Backend Manual](docs/cascor/CASCOR_BACKEND_MANUAL.md) - Complete integration guide
- [CasCor Backend Reference](docs/cascor/CASCOR_BACKEND_REFERENCE.md) - Technical API reference

### CI/CD Documentation

- [CI/CD Quick Start](docs/ci_cd/CICD_QUICK_START.md) - Get CI/CD running in 5 minutes
- [CI/CD Environment Setup](docs/ci_cd/CICD_ENVIRONMENT_SETUP.md) - Complete CI/CD environment configuration
- [CI/CD Manual](docs/ci_cd/CICD_MANUAL.md) - Comprehensive CI/CD usage guide
- [CI/CD Reference](docs/ci_cd/CICD_REFERENCE.md) - CI/CD technical reference

### Demo Mode Documentation

- [Demo Mode Quick Start](docs/demo/DEMO_MODE_QUICK_START.md) - Start demo mode in 5 minutes
- [Demo Mode Environment Setup](docs/demo/DEMO_MODE_ENVIRONMENT_SETUP.md) - Demo mode configuration
- [Demo Mode Manual](docs/demo/DEMO_MODE_MANUAL.md) - Complete demo mode guide
- [Demo Mode Reference](docs/demo/DEMO_MODE_REFERENCE.md) - Demo mode technical reference

### Testing Documentation

- [Testing Quick Start](docs/testing/TESTING_QUICK_START.md) - Run tests in 5 minutes
- [Testing Environment Setup](docs/testing/TESTING_ENVIRONMENT_SETUP.md) - Test environment configuration
- [Testing Manual](docs/testing/TESTING_MANUAL.md) - Comprehensive testing guide
- [Testing Reference](docs/testing/TESTING_REFERENCE.md) - Testing technical reference
- [Testing Reports Coverage](docs/testing/TESTING_REPORTS_COVERAGE.md) - Coverage analysis and reports
- [Testing Analysis Report](docs/testing/TESTING_ANALYSIS_REPORT.md) - Test suite analysis
- [Test Enablement Quick Reference](docs/testing/TEST_ENABLEMENT_QUICK_REFERENCE.md) - Quick test enablement guide
- [Selective Test Guide](docs/testing/SELECTIVE_TEST_GUIDE.md) - Run specific test subsets
- [Selective Test Enablement Summary](docs/testing/SELECTIVE_TEST_ENABLEMENT_SUMMARY.md) - Test enablement overview

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0
