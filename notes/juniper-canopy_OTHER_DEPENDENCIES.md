# Juniper Canopy - Other Dependencies

**Project**: Juniper
**Application**: juniper-canopy
**Last Updated**: 2026-02-25

---

## Overview

This document tracks dependencies that are **not** managed by pip or conda/mamba.
For pip-managed dependencies, see `conf/requirements_ci.txt`.
For conda/mamba-managed dependencies, see `conf/conda_environment_ci.yaml`.

---

## System Dependencies

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| CUDA Toolkit | >=11.8 | apt / nvidia | GPU acceleration (optional, for CasCor backend) |
| cuDNN | >=8.6 | apt / nvidia | Deep learning primitives (optional) |

## Build & Packaging Tools

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| build | >=1.0.0 | pip | Python package builder |
| setuptools | >=61.0 | pip | Build backend |
| wheel | latest | pip | Wheel format support |

## CI/CD Dependencies

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| GitHub Actions | N/A | github | CI/CD platform |
| actions/checkout | v4 | github-action | Repository checkout |
| actions/setup-python | v5 | github-action | Python environment setup |
| actions/upload-artifact | v4 | github-action | CI artifact storage |
| actions/cache | v4 | github-action | Dependency caching |
| conda-incubator/setup-miniconda | v3 | github-action | Conda/Miniforge setup in CI |
| gitleaks/gitleaks-action | v2 | github-action | Secrets detection |
| github/codeql-action/upload-sarif | v3 | github-action | SARIF security upload |

## Pre-commit Hooks

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| pre-commit | latest | pip | Git hook framework |
| black | latest | pip (via pre-commit) | Code formatting |
| isort | latest | pip (via pre-commit) | Import sorting |
| flake8 | latest | pip (via pre-commit) | Linting |
| mypy | latest | pip (via pre-commit) | Type checking |
| bandit | latest | pip (via pre-commit) | Security linting |

## Web/Frontend Dependencies

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| Web Browser | modern | system | Dashboard rendering (Dash/Plotly frontend) |

## Development Tools

| Dependency | Version | Management Method | Purpose |
|------------|---------|-------------------|---------|
| git | >=2.30 | apt / system | Version control |
| conda / mamba | latest | miniforge3 | Environment management |
| Docker | >=20.10 | apt / system | Containerization (optional) |
| Docker Compose | >=2.0 | apt / system | Multi-container orchestration (optional) |

## Notes

- CUDA/cuDNN are optional; the dashboard can operate in demo mode without a GPU backend.
- The shared `JuniperPython` conda environment is managed at the ecosystem level.
- Docker is used for optional containerized deployment via `conf/docker-compose.yaml`.
- The Dash/Plotly web framework is pip-managed and listed in `conf/requirements_ci.txt`.
