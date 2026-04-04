# CI/CD Technical Reference

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

---

## Table of Contents

- [Workflow Files](#workflow-files)
- [Primary Pipeline (`ci.yml`)](#primary-pipeline-ciyml)
- [Local CI-Parity Commands](#local-ci-parity-commands)
- [Dependency and Lockfile Contracts](#dependency-and-lockfile-contracts)
- [Documentation Link Validation Contract](#documentation-link-validation-contract)
- [Artifacts](#artifacts)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Workflow Files

| Workflow | File | Purpose |
| --- | --- | --- |
| Main CI pipeline | `.github/workflows/ci.yml` | Pre-commit, tests, security, build, lockfile/docs checks, Docker smoke test, quality gate |
| Dependabot lock sync | `.github/workflows/lockfile-update.yml` | Regenerates `requirements.lock` for `dependabot/pip/**` branches |
| Scheduled security scan | `.github/workflows/security-scan.yml` | Weekly/manual Bandit + pip-audit |
| Publish pipeline | `.github/workflows/publish.yml` | Release-triggered build, TestPyPI publish/verify, then PyPI publish |

---

## Primary Pipeline (`ci.yml`)

### Trigger Summary

- `push`: `main`, `develop`, `feature/**`, `fix/**`
- `pull_request`: `main`, `develop`
- `repository_dispatch`: `data-client-updated`, `cascor-client-updated`
- `workflow_dispatch`

### Job Graph

| Job | Depends On | Core Command/Action | Notes |
| --- | --- | --- | --- |
| `pre-commit` | - | `pre-commit run --all-files` | Python matrix `3.12`, `3.13`, `3.14` |
| `unit-tests` | `pre-commit` | `python -m pytest ... src/tests/unit/ src/tests/regression/` | Coverage gate at `80` |
| `integration-tests` | `unit-tests` | `python -m pytest ... src/tests/integration` | PR + main/develop only |
| `build` | `unit-tests` | `python -m build --sdist --wheel` | Uploads `dist/` |
| `security` | `pre-commit` | gitleaks + bandit + pip-audit | Fails on pip-audit vulns |
| `dependency-docs` | `build` | `bash scripts/generate_dep_docs.sh` | Uploads generated dependency docs |
| `lockfile-check` | - | `uv pip compile ... -o /tmp/requirements.lock.check` + diff | Enforces lock freshness |
| `docs` | - | `python scripts/check_doc_links.py ... --cross-repo skip` | Enforces in-repo doc links |
| `docker-build` | `build` | `docker build` + container health smoke test | PR + main/develop only |
| `required-checks` | all quality jobs | Shell assertions over `needs.*.result` | Blocking quality gate |
| `notify` | `required-checks` | Summary output | Final workflow summary |

### Test Execution Contract

Run from repository root. CI intentionally targets `src/tests/...` paths from root to keep coverage omit patterns stable.

Unit/regression command shape:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=src --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

Integration command shape:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose --timeout=120 --maxfail=3
```

---

## Local CI-Parity Commands

```bash
# 1) Install CI dependency set + editable package
python -m pip install --upgrade pip
pip install -r conf/requirements_ci.txt
pip install -e .

# 2) Run local quality checks
pre-commit run --all-files

# 3) Run unit/regression fast subset with coverage gate
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=src --cov-report=term-missing --cov-fail-under=80

# 4) Run integration fast subset
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose --timeout=120 --maxfail=3
```

---

## Dependency and Lockfile Contracts

### CI Dependency Source of Truth

- CI installs `conf/requirements_ci.txt` plus `pip install -e .`.
- `conf/requirements_ci.txt` must include dependencies required for test collection/runtime paths used in CI jobs.
- `pyproject.toml` optional dependency group `observability` includes:
  - `prometheus-client>=0.20.0`
  - `sentry-sdk>=2.0.0`

### Lockfile Freshness Contract

`requirements.lock` must be reproducible from `pyproject.toml` with all current extras used by CI:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

CI compares lockfile body only (header comment stripped) because `uv` embeds output path in header comments.

---

## Documentation Link Validation Contract

CI docs validation command:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

Key behavior:

- Internal relative links are validated and fail CI on breakage.
- Cross-repo links are intentionally skipped in CI mode.
- Supports `--cross-repo warn` and `--cross-repo check` for local audits.

---

## Artifacts

`ci.yml` publishes these artifact groups:

- `coverage-report-py<version>`: coverage XML + HTML outputs
- `unit-test-results-py<version>`: unit/regression junit XML
- `integration-test-results`: integration junit XML
- `dist-packages`: build outputs from `python -m build`
- `security-reports`: Bandit/pip-audit outputs
- `dependency-docs`: generated dependency documentation files

---

## Troubleshooting

### `ModuleNotFoundError: sentry_sdk` or `prometheus_client` in CI/local parity runs

Install CI requirements:

```bash
pip install -r conf/requirements_ci.txt
```

### Coverage unexpectedly includes tests

Run pytest from repository root using `src/tests/...` paths (CI behavior).

### Lockfile check fails despite compile

Verify compile command includes `--extra observability` and compare file body (not header).

### Docs validation fails on cross-repo links

Use CI mode locally: `--cross-repo skip`.

---

## References

- [Main CI Workflow](../../.github/workflows/ci.yml)
- [Dependabot Lockfile Update](../../.github/workflows/lockfile-update.yml)
- [Scheduled Security Scan](../../.github/workflows/security-scan.yml)
- [Publish Workflow](../../.github/workflows/publish.yml)
- [Doc Link Validator](../../scripts/check_doc_links.py)
- [Project Config](../../pyproject.toml)
