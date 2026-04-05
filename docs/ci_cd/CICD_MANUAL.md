# CI/CD Manual

**Last Updated:** 2026-04-05  
**Version:** 0.26.1  
**Status:** Current

Practical operating guide for developers, reviewers, and maintainers using the active CI workflows.

---

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Behavior](#pipeline-behavior)
3. [Developer Workflow](#developer-workflow)
4. [Reviewer Workflow](#reviewer-workflow)
5. [Maintainer Workflow](#maintainer-workflow)
6. [Failure Triage Runbook](#failure-triage-runbook)
7. [Artifacts and Diagnostics](#artifacts-and-diagnostics)
8. [Security and Release Workflows](#security-and-release-workflows)
9. [References](#references)

---

## Overview

Primary CI source of truth:

- `.github/workflows/ci.yml`

Related workflows:

- `.github/workflows/security-scan.yml` (scheduled weekly scan)
- `.github/workflows/publish.yml` (release publishing)

Current CI characteristics:

- Runners: `ubuntu-latest`
- Python matrix: `3.12`, `3.13`, `3.14` for `pre-commit` and `unit-tests`
- Single Python: `3.14` for integration/security/build/docs/lockfile/dependency-docs
- Install model: `pip` + `conf/requirements_ci.txt` + editable install (`pip install -e .`)
- Coverage enforcement: `--cov-fail-under=80`
- No Codecov upload in current workflow

---

## Pipeline Behavior

### Triggers

`CI/CD Pipeline` runs on:

- `push` to `main`, `develop`, `feature/**`, `fix/**`
- `pull_request` targeting `main` or `develop`
- `repository_dispatch` (`data-client-updated`, `cascor-client-updated`)
- `workflow_dispatch`

### Job Graph

Main jobs in execution order/dependency chains:

1. `pre-commit`
2. `unit-tests` (needs `pre-commit`)
3. `integration-tests` (needs `unit-tests`; PR/main/develop only)
4. `build` (needs `unit-tests`)
5. `security` (needs `pre-commit`)
6. `dependency-docs` (needs `build`)
7. `lockfile-check`
8. `docs`
9. `docker-build` (needs `build`; PR/main/develop only)
10. `required-checks` (aggregates outcomes)
11. `notify`

### Quality Gate Rules

`required-checks` fails on:

- failed `pre-commit`
- failed `unit-tests`
- failed `integration-tests` (if it ran)
- failed `security`
- failed `lockfile-check`
- failed `docs`
- failed `docker-build` (if it ran)
- failed `dependency-docs` (skipped is allowed)

---

## Developer Workflow

### Before Pushing

Run the same core checks locally:

```bash
python -m pip install --upgrade pip
pip install -r conf/requirements_ci.txt
pip install -e .
pip install pre-commit

pre-commit run --all-files

python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

Optional integration parity check:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose
```

### Push and Validate

```bash
git add .
git commit -m "docs: <summary>"
git push origin <branch>
```

After push, confirm CI jobs complete and check:

- matrix failures isolated to one Python version
- lockfile freshness status
- docs link validation status
- Docker smoke test status on PRs

---

## Reviewer Workflow

Reviewers should verify:

- `required-checks` is green
- coverage gate is passing (80 threshold enforced by CI command)
- no skipped critical jobs unexpectedly (except intentionally conditional jobs)
- artifacts exist for failing runs when debugging is needed

Reviewer prompts to use on failures:

- "Please rerun local pre-commit and unit/regression coverage command from `docs/ci_cd/CICD_QUICK_START.md`."
- "Please include lockfile regeneration if `lockfile-check` failed."

---

## Maintainer Workflow

### Routine Operations

Keep these aligned with source code:

- Python versions in `ci.yml` and docs
- install commands (`requirements_ci.txt`, editable install)
- marker-gating assumptions used by `src/tests/conftest.py`
- lockfile compile command and extras

### Common Maintenance Tasks

Lockfile refresh:

```bash
pip install uv
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

Docs link check used by CI:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

---

## Failure Triage Runbook

### `pre-commit` Failure

Run:

```bash
pre-commit run --all-files --show-diff-on-failure
```

### `unit-tests` Failure

Run CI-equivalent command:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --timeout=60 --maxfail=5 \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

### `integration-tests` Failure

Run:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --timeout=120 --maxfail=3
```

### `lockfile-check` Failure

Regenerate `requirements.lock` using the command in [Maintainer Workflow](#maintainer-workflow), then commit the updated lockfile.

### `docs` Failure

Run the docs link command from [Maintainer Workflow](#maintainer-workflow) and fix broken links/anchors.

### `docker-build` Failure

Reproduce locally:

```bash
docker build -t juniper-canopy:test .
docker run --rm -p 8050:8050 juniper-canopy:test
curl -sf http://localhost:8050/v1/health
```

---

## Artifacts and Diagnostics

Common artifacts from `ci.yml`:

- `coverage-report-py<version>` (coverage XML + HTML, 30 days)
- `unit-test-results-py<version>` (JUnit XML, 30 days)
- `integration-test-results` (JUnit XML, 30 days)
- `security-reports` (bandit/pip-audit outputs, 30 days)
- `dist-packages` (build artifacts, 30 days)
- `dependency-docs` (dependency snapshots, 90 days)

For failures, inspect uploaded artifacts before attempting speculative fixes.

---

## Security and Release Workflows

### Scheduled Security

`.github/workflows/security-scan.yml`:

- schedule: weekly Monday 06:00 UTC
- manual trigger: supported
- tools: `bandit` + `pip-audit`

### Publish Workflow

`.github/workflows/publish.yml`:

- trigger: `release.published`
- stages: `build` -> `testpypi` -> `pypi`
- auth model: OIDC trusted publishing (`id-token: write`)
- package verification: TestPyPI install check before PyPI publish

---

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [Testing Environment Setup](../testing/TESTING_ENVIRONMENT_SETUP.md)
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
