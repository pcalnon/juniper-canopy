# CI/CD Environment Setup Guide

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

Environment setup for reproducing current CI behavior from `.github/workflows/ci.yml`.

---

## Table of Contents

1. [Overview](#overview)
2. [Local Baseline Environment](#local-baseline-environment)
3. [CI Dependency Model](#ci-dependency-model)
4. [Test And Coverage Setup](#test-and-coverage-setup)
5. [Lockfile And Docs Gates](#lockfile-and-docs-gates)
6. [Workflow Triggers And Job Graph](#workflow-triggers-and-job-graph)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The main CI pipeline uses:

- `ubuntu-latest` GitHub-hosted runners
- Python matrix: `3.12`, `3.13`, `3.14` for `pre-commit` and `unit-tests`
- Python `3.14` for integration/security/build/docs/lockfile jobs
- `pip` installs from `conf/requirements_ci.txt` plus editable install `pip install -e .`
- CPU-only PyTorch via `https://download.pytorch.org/whl/cpu`

The pipeline is intentionally pip-first for portability.

---

## Local Baseline Environment

Use this local setup to approximate CI:

```bash
python -m pip install --upgrade pip
pip install pre-commit uv
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Create output directories used by CI jobs:

```bash
mkdir -p logs src/logs reports/junit reports/coverage reports/htmlcov reports/security
```

---

## CI Dependency Model

### `requirements_ci.txt`

CI installs from `conf/requirements_ci.txt` rather than `conf/requirements.txt`.
This file includes:

- testing tooling (`pytest`, `pytest-cov`, `pytest-timeout`, `pytest-asyncio`, `pytest-html`, `pytest-mock`)
- linting and pre-commit dependencies
- runtime dependencies used in app startup/import paths

PyTorch is installed separately with CPU-only wheels before installing `requirements_ci.txt`.

### Editable install

CI runs:

```bash
pip install -e .
```

This ensures package-style imports and source-tree path behavior match runtime expectations.

---

## Test And Coverage Setup

### Unit + regression fast subset

Equivalent to CI `unit-tests`:

```bash
cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=../reports/junit/junit-unit.xml \
  --cov=. \
  --cov-report=term-missing \
  --cov-report=xml:../reports/coverage.xml \
  --cov-report=html:../reports/htmlcov \
  --cov-fail-under=80
```

### Integration fast subset

Equivalent to CI `integration-tests`:

```bash
cd src
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose \
  --timeout=120 \
  --maxfail=3 \
  --junitxml=../reports/junit/junit-integration.xml
```

---

## Lockfile And Docs Gates

### Lockfile freshness

CI compares `requirements.lock` to a fresh compile that includes project extras:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
diff -u requirements.lock /tmp/requirements.lock.check
```

If diff is non-empty, regenerate:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Documentation links

CI validates markdown links through `scripts/check_doc_links.py` with targeted exclusions:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

Use `--cross-repo warn` locally when you want visibility into skipped cross-repo references without failing.

---

## Workflow Triggers And Job Graph

### Main pipeline trigger summary

`ci.yml` runs on:

- push to `main`, `develop`, `feature/**`, `fix/**`
- pull requests targeting `main` and `develop`
- `repository_dispatch` types `data-client-updated`, `cascor-client-updated`
- manual dispatch

### Job dependency notes

- `unit-tests` depends on `pre-commit`
- `integration-tests` depends on `unit-tests`
- `build` depends on `unit-tests`
- `dependency-docs` depends on `build`
- `required-checks` aggregates all required jobs and enforces final gate

---

## Troubleshooting

### Dependency mismatch

Symptom: import failures in CI but not local.

Checks:

```bash
python --version
pip freeze | rg "pytest|fastapi|dash|uvicorn|torch"
```

Then reinstall exactly like CI:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

### Lockfile check failure

Symptom: CI reports stale `requirements.lock`.

Fix:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Docs job failure

Symptom: broken markdown link(s) reported.

Fix workflow:

1. Run `python scripts/check_doc_links.py --cross-repo skip`.
2. Resolve path or anchor issues in reported file.
3. Re-run link checker before pushing.

---

## Related Docs

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
