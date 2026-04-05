# CI/CD Technical Reference

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

Technical reference for the GitHub Actions pipelines used by Juniper Canopy.

---

## Table of Contents

1. [Workflow Files](#workflow-files)
2. [Main CI Pipeline](#main-ci-pipeline)
3. [Lockfile Automation Pipeline](#lockfile-automation-pipeline)
4. [Dependency and Lockfile Contracts](#dependency-and-lockfile-contracts)
5. [Documentation Link Validation Contract](#documentation-link-validation-contract)
6. [Artifacts](#artifacts)
7. [Troubleshooting](#troubleshooting)

---

## Workflow Files

| Workflow | File | Purpose |
| --- | --- | --- |
| CI/CD Pipeline | `.github/workflows/ci.yml` | Primary quality gate (pre-commit, tests, security, build, docs, lockfile, docker smoke test) |
| Update Lockfile (Dependabot) | `.github/workflows/lockfile-update.yml` | Regenerates `requirements.lock` on dependabot `pip` branches |
| Publish | `.github/workflows/publish.yml` | Package publishing and release workflow |
| Security Scan | `.github/workflows/security-scan.yml` | Scheduled/triggered security scanning |

---

## Main CI Pipeline

### Triggers

Defined in `.github/workflows/ci.yml`:

- `push` to `main`, `develop`, `feature/**`, `fix/**`
- `pull_request` targeting `main` or `develop`
- `repository_dispatch` types: `data-client-updated`, `cascor-client-updated`
- `workflow_dispatch`

### Global Environment

```yaml
env:
  ENV_NAME: juniper-canopy
  PYTHON_TEST_VERSION: "3.14"
  COVERAGE_FAIL_UNDER: "80"
```

### Python Matrix

Used by `pre-commit` and `unit-tests`:

```yaml
matrix:
  python-version: ["3.12", "3.13", "3.14"]
```

### Jobs and Dependencies

| Job | Depends On | Notes |
| --- | --- | --- |
| `pre-commit` | none | Runs code-quality hooks across 3 Python versions |
| `unit-tests` | `pre-commit` | Runs fast unit/regression tests with coverage gate |
| `integration-tests` | `unit-tests` | Runs fast integration subset |
| `build` | `unit-tests` | Builds sdist/wheel |
| `security` | `pre-commit` | Gitleaks, Bandit SARIF, pip-audit |
| `dependency-docs` | `build` | Generates dependency documentation artifacts |
| `lockfile-check` | none | Verifies `requirements.lock` freshness via `uv` |
| `docs` | none | Validates internal markdown links |
| `docker-build` | `build` | Builds image and performs smoke checks |
| `required-checks` | all above | Final blocking quality gate |
| `notify` | `required-checks` | End-of-pipeline summary |

### Unit Test Command (CI Canonical)

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
  --cov-fail-under=${COVERAGE_FAIL_UNDER}
```

### Python 3.12 SIGABRT Handling

The unit-test job explicitly handles rare `pytest` exit code `134` on Python 3.12 by inspecting `reports/junit/junit-unit.xml`:

- If `failures == 0` and `errors == 0`, CI treats the run as success.
- Otherwise, the original non-zero exit code is preserved.

This behavior is implemented in `.github/workflows/ci.yml` and should be mirrored only when reproducing CI behavior exactly.

---

## Lockfile Automation Pipeline

Workflow file: `.github/workflows/lockfile-update.yml`

### Trigger and Guard

- Trigger: `push` to `dependabot/pip/**`
- Guard: `if: github.actor == 'dependabot[bot]'`

### Regeneration Command

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  -o /tmp/requirements.lock.check

mv /tmp/requirements.lock.check requirements.lock
```

### Commit Behavior

- Stages only `requirements.lock`
- Commits only when lockfile changed
- Uses commit message: `[dependabot skip] Update requirements.lock`

---

## Dependency and Lockfile Contracts

### `pyproject.toml` Extras Relevant to CI

- `juniper-data`
- `juniper-cascor`
- `observability`

The `observability` extra includes:

- `prometheus-client>=0.20.0`
- `sentry-sdk>=2.0.0`

### CI Lockfile Freshness Command

The lockfile check in `.github/workflows/ci.yml` compiles with all required extras:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
```

### Header-Insensitive Comparison

`uv` embeds the output path in the first comment lines. CI strips the first two lines before diffing:

```bash
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
```

---

## Documentation Link Validation Contract

Validation script: `scripts/check_doc_links.py`  
CI job: `docs` in `.github/workflows/ci.yml`

### Canonical CI Invocation

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### Behavior Summary

- Validates relative links and same-file anchors in markdown docs
- Skips external URLs (`http`, `https`, `mailto`, etc.)
- Skips links inside fenced code blocks and inline code spans
- Enforces repository-boundary safety checks
- Supports cross-repo policies: `skip`, `warn`, `check`

In CI, `--cross-repo skip` is used because sibling Juniper repositories are not guaranteed to be present on runner filesystems.

---

## Artifacts

| Artifact | Produced By | Path | Retention |
| --- | --- | --- | --- |
| Unit JUnit XML | `unit-tests` | `reports/junit/` | 30 days |
| Unit coverage | `unit-tests` | `reports/coverage.xml`, `reports/htmlcov/` | 30 days |
| Integration JUnit XML | `integration-tests` | `reports/junit/` | 30 days |
| Security reports | `security` | `reports/security/` | 30 days |
| Build distributions | `build` | `dist/` | 30 days |
| Dependency docs | `dependency-docs` | `conf/requirements_ci*.txt`, `conf/conda_environment_ci*.yaml` | 90 days |

---

## Troubleshooting

### Lockfile freshness fails

1. Re-generate lockfile with required extras:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

2. Re-run diff locally if needed:

```bash
uv pip compile pyproject.toml --extra juniper-data --extra juniper-cascor --extra observability -o /tmp/requirements.lock.check
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
```

### Documentation links job fails

Run exactly what CI runs:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### Unit tests fail only on Python 3.12 with exit 134

Check JUnit file values:

```bash
python - <<'PY'
import xml.etree.ElementTree as ET
root = ET.parse("reports/junit/junit-unit.xml").getroot()
print("failures:", root.attrib.get("failures", "0"))
print("errors:", root.attrib.get("errors", "0"))
PY
```

If both are `0`, this aligns with the CI workaround path.
