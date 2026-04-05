# CI/CD Environment Setup

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

Complete setup and verification guide for the GitHub Actions CI environment used by JuniperCanopy.

---

## Table of Contents

1. [Overview](#overview)
2. [Runner and Python Configuration](#runner-and-python-configuration)
3. [Dependency Installation Model](#dependency-installation-model)
4. [Optional Extras and Lockfile Policy](#optional-extras-and-lockfile-policy)
5. [Documentation Link Validation](#documentation-link-validation)
6. [Required Secrets and Tokens](#required-secrets-and-tokens)
7. [Local Reproduction Checklist](#local-reproduction-checklist)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The CI pipeline is defined in `.github/workflows/ci.yml` and runs on `ubuntu-latest` with pip-based environments.

Core environment characteristics:

- Base OS: `ubuntu-latest`
- Python matrix (quality and tests): `3.12`, `3.13`, `3.14`
- Primary single-version jobs: Python `3.14`
- Dependency source for CI jobs: `conf/requirements_ci.txt`
- Test paths in CI: `src/tests/...` (not `tests/...`)

---

## Runner and Python Configuration

Use `actions/setup-python` for each job. In this repository, the matrix and default values are:

```yaml
env:
  PYTHON_TEST_VERSION: "3.14"

strategy:
  matrix:
    python-version: ["3.12", "3.13", "3.14"]
```

Jobs that run a matrix:

- `pre-commit`
- `unit-tests`

Jobs pinned to a single Python version (`3.14`):

- `integration-tests`
- `build`
- `security`
- `dependency-docs`
- `lockfile-check`
- `docs`

---

## Dependency Installation Model

CI currently uses pip installation, not conda environment activation, for workflow execution.

Canonical install sequence used in test jobs:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Notes:

- CPU-only PyTorch is intentional for runner compatibility.
- Editable install (`pip install -e .`) ensures package resolution matches source checkout behavior.

---

## Optional Extras and Lockfile Policy

`pyproject.toml` defines optional extras that are included in lockfile generation:

- `juniper-data`
- `juniper-cascor`
- `observability` (`prometheus-client`, `sentry-sdk`)

Canonical compile command:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

CI lockfile freshness behavior:

- Compiles to `/tmp/requirements.lock.check`
- Compares the file body from line 3 onward to ignore uv header path differences
- Fails if content differs

Dependabot lockfile update workflow:

- Regenerates via `/tmp/requirements.lock.check`
- Moves output to `requirements.lock`
- Commits only when diff exists

---

## Documentation Link Validation

CI includes a dedicated docs job that runs link checks:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

When reproducing locally, use the same exclusion list to match CI behavior.

---

## Required Secrets and Tokens

Required for specific workflows:

- `CROSS_REPO_DISPATCH_TOKEN`: used by lockfile update workflow for pushing lockfile commits from Dependabot branches

May be required depending on project policy:

- `CODECOV_TOKEN`: only if coverage upload to Codecov is enabled in your workflows

---

## Local Reproduction Checklist

Use this checklist when validating CI-affecting changes before pushing:

1. Install CI deps: `pip install -r conf/requirements_ci.txt`
2. Run unit/regression subset:
   `python -m pytest -m "not requires_cascor and not requires_server and not slow" src/tests/unit/ src/tests/regression/ --cov=src --cov-fail-under=80`
3. Run integration subset:
   `python -m pytest -m "integration and not requires_cascor and not requires_server and not slow" src/tests/integration`
4. Validate lockfile freshness using the canonical uv compile command.
5. Validate docs links with `scripts/check_doc_links.py` CI flags.

---

## Troubleshooting

### `requirements.lock` freshness check fails

Cause:

- `pyproject.toml` extras changed but lockfile not regenerated with all required extras.

Fix:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Documentation link validation fails in CI only

Cause:

- Local run used different exclusion/cross-repo flags than CI.

Fix:

- Re-run `scripts/check_doc_links.py` with the exact CI argument set.

### Tests pass locally but fail in CI path resolution

Cause:

- Running `pytest` from `src/` with old path assumptions (`tests/...`) instead of repository-root paths (`src/tests/...`).

Fix:

- Run commands from repository root using CI-equivalent test paths.

