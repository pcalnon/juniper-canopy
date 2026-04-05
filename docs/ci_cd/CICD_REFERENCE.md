# CI/CD Technical Reference

## Verified reference for GitHub workflows

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

1. [Workflow Files](#workflow-files)
2. [Primary Pipeline (`ci.yml`)](#primary-pipeline-ciyml)
3. [Job Contracts](#job-contracts)
4. [Lockfile and Dependency Policy](#lockfile-and-dependency-policy)
5. [Documentation Link Validation](#documentation-link-validation)
6. [Security Workflows](#security-workflows)
7. [Publish Workflow](#publish-workflow)
8. [Dependabot Lockfile Workflow](#dependabot-lockfile-workflow)

## Workflow Files

- `.github/workflows/ci.yml`: main CI pipeline used on push/PR.
- `.github/workflows/security-scan.yml`: scheduled weekly scan.
- `.github/workflows/publish.yml`: release publishing pipeline.
- `.github/workflows/lockfile-update.yml`: Dependabot lockfile update automation.

## Primary Pipeline `ci.yml`

### Triggers

```yaml
on:
  push:
    branches: [main, develop, feature/**, fix/**]
  pull_request:
    branches: [main, develop]
  repository_dispatch:
    types: [data-client-updated, cascor-client-updated]
  workflow_dispatch:
```

### Global Environment

```yaml
env:
  ENV_NAME: juniper-canopy
  PYTHON_TEST_VERSION: "3.14"
  COVERAGE_FAIL_UNDER: "80"
```

### Execution Order

```text
pre-commit
  -> unit-tests
    -> integration-tests (PR/main/develop only)
    -> build
      -> dependency-docs
      -> docker-build (PR/main/develop only)
security (after pre-commit)
lockfile-check
docs
required-checks (aggregates all required jobs)
notify
```

## Job Contracts

### `pre-commit`

- Python matrix: `3.12`, `3.13`, `3.14`
- Runs: `pre-commit run --all-files --show-diff-on-failure`
- Uses pre-commit hook cache (`~/.cache/pre-commit`)

### `unit-tests`

- Python matrix: `3.12`, `3.13`, `3.14`
- Installs:
  - `torch` (CPU index)
  - `conf/requirements_ci.txt`
  - editable package (`pip install -e .`)
- Test command:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=reports/junit/junit-unit.xml \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

- Special behavior: Python 3.12 SIGABRT (`exit 134`) is treated as success only when JUnit XML reports `0` failures and `0` errors.

### `integration-tests`

- Runs when event is PR or branch is `main`/`develop`
- Uses Python `3.14`
- Marker filter:

```bash
-m "integration and not requires_cascor and not requires_server and not slow"
```

### `build`

- Uses Python `3.14`
- Builds wheel/sdist via `python -m build`
- Verifies artifacts in `dist/`

### `security`

- Runs gitleaks, bandit (SARIF + text), and pip-audit
- Uploads SARIF with `github/codeql-action/upload-sarif`
- Fails pipeline on pip-audit vulnerabilities

### `dependency-docs`

- Uses Miniforge setup
- Installs CI dependencies and runs:

```bash
bash scripts/generate_dep_docs.sh
```

- Validates generated `conf/conda_environment_ci.yaml`

### `lockfile-check`

- Verifies `requirements.lock` freshness by recompiling with `uv`:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
```

- Compares lockfile bodies with first two header lines stripped to avoid false diffs from output-path metadata.

### `docs`

- Runs internal documentation link validation:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### `docker-build`

- Runs on PR/main/develop only
- Builds root Docker image
- Starts container and checks health endpoint `/v1/health`

### `required-checks`

- Final quality gate.
- Fails if any required upstream jobs fail (including lockfile or docs checks).

## Lockfile and Dependency Policy

- `requirements.lock` is the canonical compiled lock for CI parity.
- Compile command must include `juniper-data`, `juniper-cascor`, and `observability` extras.
- `conf/requirements_ci.txt` remains the direct CI install list for fast, deterministic setup.

## Documentation Link Validation

`scripts/check_doc_links.py` validates:

- Relative file links resolve inside repo boundaries.
- Same-file anchors map to existing headings.
- Cross-repo links are policy-controlled (`skip`, `warn`, `check`).

CI currently uses `--cross-repo skip` for portability.

## Security Workflows

### `ci.yml` `security` job

- Runs on standard CI events.
- Produces artifacts in `reports/security/`.

### `security-scan.yml`

- Trigger: weekly (`0 6 * * 1`) + manual dispatch.
- Runs:
  - `bandit` (SARIF + console output)
  - `pip-audit --strict --desc on`
- Installs package editable with dev extras: `pip install -e ".[dev]"`.

## Publish Workflow

`publish.yml` triggers on release publish and has three jobs:

1. `build` (`python -m build`, `twine check`)
2. `testpypi` (OIDC publish + install verification)
3. `pypi` (OIDC publish after TestPyPI success)

Uses pinned GitHub Action SHAs for supply-chain stability.

## Dependabot Lockfile Workflow

`lockfile-update.yml`:

- Trigger: push to `dependabot/pip/**`
- Guard: `if: github.actor == 'dependabot[bot]'`
- Regenerates `requirements.lock` using `uv pip compile`
- Commits and pushes with bot identity when lockfile changes

This keeps Dependabot dependency bumps synchronized with lockfile content.
