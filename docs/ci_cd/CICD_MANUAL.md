# CI/CD Complete User Manual

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Overview

This manual describes the **current** CI implementation in `.github/workflows/ci.yml`.

Primary goals:

- Catch regressions quickly on pull requests and branch pushes.
- Keep dependency state reproducible (`requirements.lock` freshness gate).
- Prevent documentation drift (`scripts/check_doc_links.py` gate).
- Verify packaging and container startup paths.

## Pipeline at a Glance

The `CI/CD Pipeline` workflow runs these jobs:

1. `pre-commit` (matrix: Python `3.12`, `3.13`, `3.14`)
2. `unit-tests` (matrix: Python `3.12`, `3.13`, `3.14`)
3. `integration-tests` (Python `3.14`)
4. `build` (Python `3.14`)
5. `security` (Python `3.14`)
6. `dependency-docs` (Python `3.14`, includes Miniforge for generation scripts)
7. `lockfile-check` (Python `3.14`)
8. `docs` (Python `3.14`)
9. `docker-build`
10. `required-checks` (quality gate aggregator)
11. `notify`

## Triggers and Branches

Workflow triggers:

- `push` to `main`, `develop`, `feature/**`, `fix/**`
- `pull_request` to `main`, `develop`
- `repository_dispatch` (`data-client-updated`, `cascor-client-updated`)
- `workflow_dispatch`

No path filtering is currently configured, so docs-only changes still execute CI.

## Dependency Model

For test/build jobs, CI is pip-based and uses:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Why this matters:

- The CPU-only torch install avoids GPU dependency overhead on runners.
- `conf/requirements_ci.txt` must include runtime dependencies needed in tests (for example `prometheus-client`, `sentry-sdk`).
- Editable install ensures imports resolve from this repository source tree.

## Test Selection Behavior

CI intentionally runs **fast subsets** using marker filters:

- Unit/regression job:
  - `-m "not requires_cascor and not requires_server and not slow"`
  - Paths: `src/tests/unit/ src/tests/regression/`
- Integration job:
  - `-m "integration and not requires_cascor and not requires_server and not slow"`
  - Path: `src/tests/integration`

Environment defaults used by CI jobs:

```bash
CASCOR_BACKEND_AVAILABLE=0
RUN_SERVER_TESTS=0
ENABLE_SLOW_TESTS=0
```

### Optional Client Testing Modules

Some tests need helper modules from optional client extras:

- `juniper_cascor_client.testing`
- `juniper_data_client.testing`

These are guarded with `pytest.importorskip(...)`, so collection succeeds and tests skip cleanly when extras are missing.

## Coverage and Exit Semantics

- Coverage gate for unit/regression job is `--cov-fail-under=80`.
- A Python 3.12 interpreter cleanup issue can produce `pytest` exit `134` (`SIGABRT`) after tests finish.
- CI handles this by parsing JUnit XML and treating the run as success when `failures=0` and `errors=0`.

## Documentation Link Validation

The `docs` job runs:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

This checks local docs links/anchors while skipping cross-repo validation in CI.

## Lockfile Freshness

The `lockfile-check` job recompiles from `pyproject.toml` extras and compares content with `requirements.lock` (header lines stripped before diff).

Regenerate locally when stale:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

## Docker Smoke Verification

The `docker-build` job:

1. Builds image: `docker build -t juniper-canopy:ci-${GITHUB_SHA} .`
2. Starts container on `:8050`
3. Waits for container health
4. Verifies package import
5. Calls `/v1/health`

This catches packaging/entrypoint/runtime startup regressions not visible in unit tests.

## Quality Gate Rules

`required-checks` fails the workflow when any blocking job fails, including:

- `pre-commit`
- `unit-tests`
- `integration-tests` (if run)
- `security` (failure only)
- `build`
- `docs`
- `lockfile-check`
- `docker-build` (failure only)

## Developer Runbook

Before pushing:

```bash
pre-commit run --all-files

python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src \
  --cov-report=term-missing \
  --cov-fail-under=80

python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration

python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## Troubleshooting

### Failing docs job

- Run the exact docs-check command locally.
- Fix moved files, broken relative paths, or invalid anchors.

### Failing lockfile-check

- Recompile `requirements.lock` using the command above.
- Commit both `requirements.lock` and any dependency declaration changes.

### Unexpected skipped tests for service/e2e paths

- Install optional testing extras:
  - `pip install "juniper-cascor-client[testing]"`
  - `pip install "juniper-data-client[testing]"`

### Unit job exits with `134` locally on Python 3.12

- Inspect generated JUnit XML (`reports/junit/junit-unit.xml`) for failures/errors.
- If none are present, behavior likely matches the known CI cleanup anomaly.

## Related Documentation

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
