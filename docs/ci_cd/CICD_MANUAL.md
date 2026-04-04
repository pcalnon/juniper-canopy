# CI/CD Manual

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

1. [Overview](#overview)
2. [Current Pipeline Architecture](#current-pipeline-architecture)
3. [Job-by-Job Behavior](#job-by-job-behavior)
4. [Developer Workflow](#developer-workflow)
5. [Failure Triage Runbook](#failure-triage-runbook)
6. [Common Pitfalls](#common-pitfalls)
7. [References](#references)

## Overview

This manual describes the **current** GitHub Actions pipeline implemented in `.github/workflows/ci.yml`.

The pipeline is designed for:

- Fast feedback on PRs
- Deterministic test selection and coverage gating
- Security and dependency hygiene
- Documentation link integrity
- Container build smoke validation

## Current Pipeline Architecture

### Trigger Scope

The workflow runs on:

- `push` to `main`, `develop`, `feature/**`, `fix/**`
- `pull_request` into `main` or `develop`
- `repository_dispatch` (`data-client-updated`, `cascor-client-updated`)
- `workflow_dispatch`

### High-Level Job Graph

`pre-commit` and `unit-tests` are core gates. Other jobs fan out and are aggregated by `required-checks`.

```text
pre-commit
   └── unit-tests
       ├── integration-tests
       ├── build
       │   ├── dependency-docs
       │   └── docker-build (PR/main/develop only)
       └── ...

security (depends on pre-commit)
lockfile-check (independent)
docs (independent)

required-checks waits on:
pre-commit, unit-tests, integration-tests, security, build,
dependency-docs, lockfile-check, docs, docker-build
```

## Job-by-Job Behavior

### `pre-commit`

- Runs on Python `3.12`, `3.13`, `3.14`
- Installs and executes hooks from `.pre-commit-config.yaml`
- Caches hook environments
- Fails on any hook failure

### `unit-tests`

- Runs on Python `3.12`, `3.13`, `3.14`
- Installs CPU-only PyTorch and `conf/requirements_ci.txt`
- Runs:
  - `src/tests/unit/`
  - `src/tests/regression/`
- Marker filter:
  - `not requires_cascor and not requires_server and not slow`
- Enforces coverage gate:
  - `--cov-fail-under=80`
- Uploads JUnit and coverage artifacts
- Includes a targeted workaround for Python 3.12 cleanup-time SIGABRT (`exit 134`) by checking JUnit failures/errors before failing the job

### `integration-tests`

- Depends on `unit-tests`
- Runs on PRs and `main`/`develop` pushes
- Executes:
  - `src/tests/integration`
- Marker filter:
  - `integration and not requires_cascor and not requires_server and not slow`

### `build`

- Depends on `unit-tests`
- Builds sdist/wheel via `python -m build`
- Verifies build artifacts are present in `dist/`

### `security`

- Depends on `pre-commit`
- Runs:
  - Gitleaks (secrets)
  - Bandit (SARIF + text output)
  - pip-audit (dependency vulnerabilities)

### `dependency-docs`

- Depends on `build`
- Generates dependency documentation via `scripts/generate_dep_docs.sh`
- Validates generated YAML structure

### `lockfile-check`

- Recompiles lock candidate with `uv pip compile`
- Compares body of generated lock against `requirements.lock` (header stripped to avoid path-noise diffs)
- Fails if stale

### `docs`

- Runs markdown link validation via `scripts/check_doc_links.py`
- CI mode uses `--cross-repo skip`
- Excludes high-churn/archive directories intentionally

### `docker-build`

- Depends on `build`
- Runs on PRs and `main`/`develop`
- Builds image, starts container, validates:
  - package import
  - health endpoint

### `required-checks`

- Aggregates all required job results
- Converts individual failures into one branch protection gate

## Developer Workflow

### Recommended Pre-Push Sequence

```bash
pre-commit run --all-files

mkdir -p logs src/logs reports/junit reports/htmlcov
python -m pytest -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ --cov=src --cov-fail-under=80

python -m pytest -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration

python scripts/check_doc_links.py --cross-repo skip
```

### Optional Test Extras

Some tests rely on optional test helper modules and will skip if extras are not installed.

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

## Failure Triage Runbook

### If `unit-tests` fails at collection

1. Check missing modules in traceback.
2. Install missing extras (`[testing]`) when failure references testing fixtures/clients.
3. Re-run only failing file locally with `-vv`.

### If `docs` fails

1. Run `python scripts/check_doc_links.py --cross-repo skip`.
2. Fix reported file paths or heading anchors.
3. Re-run validator before pushing.

### If `lockfile-check` fails

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

## Common Pitfalls

- Assuming CI installs optional testing extras automatically for all contexts.
- Treating `requires_cascor`/`requires_server` tests as part of default CI pass criteria.
- Editing docs without running link validation.
- Updating dependencies but forgetting to regenerate `requirements.lock`.

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [Testing Manual](../testing/TESTING_MANUAL.md)
- [Testing Reference](../testing/TESTING_REFERENCE.md)
