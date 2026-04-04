# CI/CD Reference

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

- [Workflow File](#workflow-file)
- [Job Matrix and Ordering](#job-matrix-and-ordering)
- [Test Selection Contracts](#test-selection-contracts)
- [Coverage and Exit Behavior](#coverage-and-exit-behavior)
- [Documentation Link Validation](#documentation-link-validation)
- [Lockfile Freshness](#lockfile-freshness)
- [Artifacts](#artifacts)
- [Local Equivalents](#local-equivalents)

## Workflow File

- Main pipeline: `.github/workflows/ci.yml`
- Workflow name: `CI/CD Pipeline`
- Triggers:
  - `push`: `main`, `develop`, `feature/**`, `fix/**`
  - `pull_request`: `main`, `develop`
  - `repository_dispatch`: `data-client-updated`, `cascor-client-updated`
  - `workflow_dispatch`

## Job Matrix and Ordering

### Matrix jobs

- `pre-commit`: Python `3.12`, `3.13`, `3.14`
- `unit-tests`: Python `3.12`, `3.13`, `3.14`

### Non-matrix jobs

- `integration-tests` (runs on PRs and `main`/`develop`)
- `build`
- `security`
- `dependency-docs`
- `lockfile-check`
- `docs`
- `docker-build` (runs on PRs and `main`/`develop`)
- `required-checks`
- `notify`

## Test Selection Contracts

### Unit/regression in CI

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/
```

### Integration in CI

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration
```

### Environment flags set in CI

- `CASCOR_BACKEND_AVAILABLE=0`
- `RUN_SERVER_TESTS=0`
- `ENABLE_SLOW_TESTS=0`

These flags and marker expressions are the source of truth for CI test scope.

## Coverage and Exit Behavior

- Coverage gate is enforced in `unit-tests` via:
  - `--cov=src`
  - `--cov-fail-under=80`
- Special handling exists for Python `3.12` exit code `134`:
  - If pytest exits `134` but JUnit XML reports `failures=0` and `errors=0`, CI treats the run as success.
  - This prevents false-failures from interpreter cleanup SIGABRT behavior.

## Documentation Link Validation

Validator script: `scripts/check_doc_links.py`

CI invocation:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

Key behavior:

- Validates relative markdown file links and heading anchors
- Skips links inside fenced code blocks and inline code spans
- Supports cross-repo policies: `skip`, `warn`, `check`
- Enforces repository-boundary and traversal-safety checks

## Lockfile Freshness

`lockfile-check` compares the body of committed `requirements.lock` to a fresh compile:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
```

Header lines are excluded intentionally so output-path metadata does not create false diffs.

## Artifacts

- Coverage: `coverage-report-py<version>`
  - `reports/coverage.xml`
  - `reports/htmlcov/`
- Unit results: `unit-test-results-py<version>`
  - `reports/junit/`
- Integration results: `integration-test-results`
- Security reports: `security-reports`
- Build outputs: `dist-packages`
- Dependency docs: `dependency-docs`

## Local Equivalents

- Full docs check: `python scripts/check_doc_links.py --cross-repo skip`
- Unit CI parity: use `-m "not requires_cascor and not requires_server and not slow"` on `src/tests/unit/ src/tests/regression/`
- Integration CI parity: use `-m "integration and not requires_cascor and not requires_server and not slow"` on `src/tests/integration`
