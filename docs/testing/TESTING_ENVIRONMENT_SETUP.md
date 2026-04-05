# Testing Environment Setup

**Last Updated:** 2026-04-04  
**Version:** v0.26.0  
**Status:** Current

Environment setup guide for running Juniper Canopy tests with behavior aligned to current CI and marker gating.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Creation](#environment-creation)
3. [Install Dependencies](#install-dependencies)
4. [Optional Testing Extras](#optional-testing-extras)
5. [Directory and Output Setup](#directory-and-output-setup)
6. [Verification Commands](#verification-commands)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

- Python `3.12+` recommended for local parity with active CI matrix
- `pip` and Git installed
- Repository checked out and up to date

## Environment Creation

Use your preferred environment manager (`venv`, Conda, or equivalent). Example with `venv`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## Install Dependencies

Install the same baseline dependencies used by CI test jobs:

```bash
# CPU-only torch for test/runtime parity
pip install torch --index-url https://download.pytorch.org/whl/cpu

# CI-aligned package set
pip install -r conf/requirements_ci.txt

# Editable project install
pip install -e .
```

## Optional Testing Extras

Some tests use `pytest.importorskip(...)` for optional helper modules and will skip if these extras are absent.

Install optional testing extras when validating the full surface:

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

Common gated modules:

- `juniper_cascor_client.testing`
- `juniper_data_client.testing`

Typical tests affected:

- Service-mode control/connection tests using fake CasCor clients
- Dataset/versioning and E2E data pipeline tests using fake data clients

## Directory and Output Setup

Create expected output directories before running full local checks:

```bash
mkdir -p logs src/logs reports/junit reports/coverage reports/htmlcov reports/security
```

## Verification Commands

Run these checks to verify environment health and CI-style behavior:

```bash
# Toolchain sanity
python --version
pytest --version
pre-commit --version

# Unit + regression fast subset (CI parity)
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-fail-under=80

# Integration fast subset (CI parity)
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration
```

If you need to validate documentation checks in the same local run:

```bash
python scripts/check_doc_links.py --cross-repo skip
```

## Troubleshooting

### `ModuleNotFoundError` for testing helper modules

Install optional extras:

```bash
pip install "juniper-cascor-client[testing]" "juniper-data-client[testing]"
```

### Many tests appear as skipped

This is often expected when:

- marker-gated tests require live services (`requires_cascor`, `requires_server`)
- optional testing extras are not installed (`pytest.importorskip`)

List active markers:

```bash
pytest --markers
```

### CI parity mismatch for lockfile checks

Regenerate lockfile with CI extras:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

