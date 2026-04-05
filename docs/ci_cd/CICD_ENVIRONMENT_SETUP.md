# CI/CD Environment Setup

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

Source-aligned configuration guide for the active GitHub Actions CI pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Workflow Topology](#workflow-topology)
3. [Runtime Environments](#runtime-environments)
4. [Dependency Installation Model](#dependency-installation-model)
5. [CI Environment Variables](#ci-environment-variables)
6. [Artifacts and Retention](#artifacts-and-retention)
7. [Security and Permissions](#security-and-permissions)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The primary workflow is `.github/workflows/ci.yml`.

Current defaults:

- Runner: `ubuntu-latest`
- CI Python matrix: `3.12`, `3.13`, `3.14` (pre-commit + unit tests)
- Integration/security/build/docs/lockfile jobs: Python `3.14`
- Dependency model: `pip` + `conf/requirements_ci.txt` + editable install (`pip install -e .`)
- Coverage gate: `80%` (`--cov-fail-under=80`)

---

## Workflow Topology

`CI/CD Pipeline` includes these jobs:

1. `pre-commit`
2. `unit-tests`
3. `integration-tests`
4. `build`
5. `security`
6. `dependency-docs`
7. `lockfile-check`
8. `docs`
9. `docker-build`
10. `required-checks`
11. `notify`

Key dependencies:

- `unit-tests` depends on `pre-commit`
- `integration-tests` depends on `unit-tests`
- `build` depends on `unit-tests`
- `dependency-docs` and `docker-build` depend on `build`
- `required-checks` aggregates pass/fail across all gate jobs

---

## Runtime Environments

### Python Versions

- Pre-commit: `3.12`, `3.13`, `3.14`
- Unit tests: `3.12`, `3.13`, `3.14`
- Integration tests: `3.14`
- Security scans: `3.14`
- Build/docs/lockfile/dependency-docs: `3.14`

### Trigger Conditions

- Push: `main`, `develop`, `feature/**`, `fix/**`
- Pull request: `main`, `develop`
- `repository_dispatch` for dependency client updates
- Manual: `workflow_dispatch`

Conditional jobs:

- `integration-tests` and `docker-build` run for PRs and `main`/`develop` pushes.

---

## Dependency Installation Model

CI no longer uses Conda for core test/build jobs.

Canonical install sequence (used in test jobs):

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Notes:

- CPU-only torch keeps CI deterministic and lightweight for runner constraints.
- Editable install ensures package imports resolve from the checked-out source tree.
- `actions/setup-python` uses `cache: pip` in most jobs.

`dependency-docs` is the exception: it initializes Miniforge to generate dependency docs artifacts, but test/build correctness still relies on pip installations.

- CI installs CPU-only torch explicitly.
- `conf/requirements_ci.txt` now includes `prometheus-client` and `sentry-sdk` used by observability paths.
- Editable install (`-e .`) ensures imports resolve from the source tree.

## CI Environment Variables

Top-level env values in `ci.yml`:

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

Common job-scoped test gating flags:

```yaml
CASCOR_BACKEND_AVAILABLE: 0
RUN_SERVER_TESTS: 0
ENABLE_SLOW_TESTS: 0
```

Why these matter:

- Prevents infra-dependent tests from blocking default CI.
- Keeps CI focused on deterministic fast suites.
- Matches marker behavior in `src/tests/conftest.py`.

- CI remains green without `*[testing]` extras.
- These tests are skipped instead of failing collection.

## Artifacts and Retention

Use `--cross-repo check` locally when sibling Juniper repositories are checked out and you want full ecosystem link validation.

---

- Coverage XML + HTML: `coverage-report-py<version>` (30 days)
- JUnit XML: `unit-test-results-py<version>` and `integration-test-results` (30 days)
- Security reports: `security-reports` (30 days)
- Dist packages: `dist-packages` (30 days)
- Dependency docs: `dependency-docs` (90 days)

Artifact publishing uses `if: always()` where post-failure diagnostics are needed.

This validates internal links/anchors while skipping cross-repo link checks in CI.

## Security and Permissions

Top-level CI workflow permissions:

```yaml
permissions:
  contents: read
```

Security job elevates:

```yaml
permissions:
  contents: read
  security-events: write
```

Security scan behavior:

- `gitleaks` fails on detected secrets.
- `bandit` emits SARIF and text reports (SARIF uploaded to GitHub Security).
- `pip-audit` currently runs on an explicitly installed package subset in `ci.yml` security job.

Lockfile correctness:

- `lockfile-check` recompiles `requirements.lock` with extras:
  - `juniper-data`
  - `juniper-cascor`
  - `observability`

Default retention is 30 days (90 for dependency docs).

## Troubleshooting

Coverage gate failing:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

Lockfile mismatch:

```bash
pip install uv
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

Security job differs from local audit:

- Reproduce local environment with `conf/requirements_ci.txt` and `pip install -e .`
- Run `bandit -r src -c .bandit.yml`
- Run `pip-audit --strict --desc on`

---

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
