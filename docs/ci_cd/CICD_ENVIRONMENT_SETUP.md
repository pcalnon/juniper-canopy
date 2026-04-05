# CI/CD Environment Setup

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

Environment setup guide for reproducing CI behavior locally and understanding how GitHub Actions runners are configured.

## Table of Contents

1. [Overview](#overview)
2. [Runner Environment](#runner-environment)
3. [Local Environment Parity](#local-environment-parity)
4. [Dependencies](#dependencies)
5. [Optional Test Extras](#optional-test-extras)
6. [Required Directories](#required-directories)
7. [Verification Commands](#verification-commands)
8. [Troubleshooting](#troubleshooting)

## Overview

The CI pipeline in `.github/workflows/ci.yml` is pip-first (not Conda-first) for most jobs.

- Python versions tested for quality and unit gate: `3.12`, `3.13`, `3.14`
- Main dependencies source: `conf/requirements_ci.txt`
- Project install mode in CI test jobs: editable (`pip install -e .`)
- Coverage threshold in unit gate: `80%`
- Integration gate: fast subset only (`integration and not requires_cascor and not requires_server and not slow`)

## Runner Environment

CI uses GitHub-hosted Ubuntu runners and `actions/setup-python`.

- OS: `ubuntu-latest`
- Python setup: `actions/setup-python`
- Caching: pip cache (`cache: pip`) plus pre-commit hook cache
- Torch install in CI: CPU-only index (`https://download.pytorch.org/whl/cpu`)

Conda is used only in the `dependency-docs` job to run dependency documentation generation and validate `conf/conda_environment_ci.yaml`.

## Local Environment Parity

Use a clean virtual environment (or your project environment) and run:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

## Dependencies

CI dependencies are documented in:

- `conf/requirements_ci.txt`
- `pyproject.toml` (core + optional extras)
- `requirements.lock` (freshness enforced by `lockfile-check` job)

Lockfile freshness command used by CI:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

## Optional Test Extras

Some tests are intentionally gated and skip unless optional testing extras are installed.

Install extras for local full-surface validation:

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

Why this matters:

- Several tests use `pytest.importorskip("juniper_cascor_client.testing")`
- Several tests use `pytest.importorskip("juniper_data_client.testing")`
- Without extras, tests skip instead of failing collection

This behavior keeps baseline CI stable while allowing deeper local/opt-in coverage.

## Required Directories

Before running the same commands CI runs, create expected output directories:

```bash
mkdir -p logs src/logs reports/junit reports/coverage reports/htmlcov reports/security
```

## Verification Commands

Run the same high-signal checks used in CI:

```bash
# Quality hooks
pre-commit run --all-files

# Unit + regression fast gate
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-fail-under=80

# Integration fast gate
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration

# Docs links
python scripts/check_doc_links.py --cross-repo skip
```

## Troubleshooting

### `ModuleNotFoundError` for `juniper_*_client.testing`

Install optional testing extras:

```bash
pip install "juniper-cascor-client[testing]" "juniper-data-client[testing]"
```

### `requirements.lock` mismatch in local checks

Regenerate lockfile exactly as CI expects:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Documentation link check failures for sibling repos

CI uses `--cross-repo skip`. Use the same mode locally unless sibling repositories are checked out.

```bash
python scripts/check_doc_links.py --cross-repo skip
```

