# CI/CD Technical Reference

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Scope

This reference documents the current CI behavior implemented in:

- `.github/workflows/ci.yml`
- `scripts/check_doc_links.py`
- `conf/requirements_ci.txt`
- `pyproject.toml`

## Workflow Summary

Workflow name: `CI/CD Pipeline`

Trigger events:

- `push` (`main`, `develop`, `feature/**`, `fix/**`)
- `pull_request` (`main`, `develop`)
- `repository_dispatch` (`data-client-updated`, `cascor-client-updated`)
- `workflow_dispatch`

Concurrency:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

## Job Specifications

### `pre-commit`

- Python matrix: `3.12`, `3.13`, `3.14`
- Installs `pre-commit`
- Runs `pre-commit run --all-files --show-diff-on-failure`
- Caches pre-commit hooks (`~/.cache/pre-commit`)

### `unit-tests`

- Python matrix: `3.12`, `3.13`, `3.14`
- Installs CPU torch and `conf/requirements_ci.txt`
- Runs:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=reports/junit/junit-unit.xml \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

Special behavior:

- Handles Python 3.12 `pytest` cleanup SIGABRT (`exit 134`) by checking JUnit `failures/errors` before deciding failure.

Artifacts:

- `coverage-report-py<version>`
- `unit-test-results-py<version>`

### `integration-tests`

- Python: `3.14`
- Runs only on PRs and pushes to `main`/`develop`
- Marker filter:

```bash
integration and not requires_cascor and not requires_server and not slow
```

Artifact:

- `integration-test-results`

### `build`

- Python: `3.14`
- Uses `python -m build --sdist --wheel`
- Verifies both `.tar.gz` and `.whl`
- Uploads `dist-packages`

### `security`

- Python: `3.14`
- Tools: `gitleaks`, `bandit`, `pip-audit`
- Uploads SARIF and security report artifacts

### `dependency-docs`

- Python: `3.14`
- Also configures Miniforge
- Runs `scripts/generate_dep_docs.sh`
- Validates generated YAML structure

Artifact:

- `dependency-docs`

### `lockfile-check`

- Python: `3.14`
- Installs `uv`
- Recompiles from `pyproject.toml` extras:
  - `juniper-data`
  - `juniper-cascor`
  - `observability`
- Strips first two header lines before diff comparison

### `docs`

- Python: `3.14`
- Runs doc link validator with excluded directories/files:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### `docker-build`

- Builds image from root `Dockerfile`
- Starts container and waits for healthy state
- Verifies:
  - package import
  - `/v1/health` response

### `required-checks`

Aggregates job results and enforces final pass/fail semantics used by branch protection.

## Environment Variables Used in CI

Top-level workflow env:

```yaml
env:
  ENV_NAME: juniper-canopy
  PYTHON_TEST_VERSION: "3.14"
  COVERAGE_FAIL_UNDER: "80"
```

Test gating envs in unit/integration jobs:

```yaml
CASCOR_BACKEND_AVAILABLE: 0
RUN_SERVER_TESTS: 0
ENABLE_SLOW_TESTS: 0
```

## Dependency Reference

Primary CI dependency file:

- `conf/requirements_ci.txt`

Notable required entries:

- `prometheus-client>=0.20.0`
- `sentry-sdk>=2.0.0`

These support observability-import paths used during tests and runtime checks.

## Documentation Link Checker Reference

Script: `scripts/check_doc_links.py`

Core capabilities:

- Validates relative file links and same-file anchors.
- Skips fenced code blocks and inline code spans.
- Supports cross-repo handling modes:
  - `skip` (CI default)
  - `warn`
  - `check`

Exit codes:

- `0`: all valid
- `1`: broken links or invalid arguments

## Common Failure Classes

### Stale lockfile

Symptom:

- `lockfile-check` fails diff

Fix:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Broken docs links

Symptom:

- `docs` job reports missing files/anchors

Fix:

- run checker locally with the CI command and repair relative paths or heading anchors

### Optional testing modules skipped

Symptom:

- Service/e2e tests skipped via `importorskip`

Fix (local full-run only):

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

## Related Docs

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Complete Manual](CICD_MANUAL.md)
