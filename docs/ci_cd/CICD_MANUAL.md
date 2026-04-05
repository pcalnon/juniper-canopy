# CI/CD Manual

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

Practical runbook for developers, reviewers, and maintainers based on the active workflows in `.github/workflows/`.

---

## Table of Contents

1. [Overview](#overview)
2. [Developer Workflow](#developer-workflow)
3. [Reviewer Workflow](#reviewer-workflow)
4. [Maintainer Workflow](#maintainer-workflow)
5. [Quality Gates And Failure Handling](#quality-gates-and-failure-handling)
6. [Common CI Failure Patterns](#common-ci-failure-patterns)
7. [Operational Best Practices](#operational-best-practices)

---

## Overview

The primary CI gate is `.github/workflows/ci.yml` and includes:

- pre-commit checks
- fast unit/regression tests with coverage threshold
- fast integration tests
- security scanning
- build/package validation
- lockfile freshness validation
- documentation link validation
- Docker build smoke test
- final aggregate gate (`required-checks`)

Additional workflows:

- `.github/workflows/security-scan.yml` for scheduled deep security scanning
- `.github/workflows/publish.yml` for release publishing
- `.github/workflows/lockfile-update.yml` for Dependabot lockfile regeneration

---

## Developer Workflow

### Before opening a PR

Run the same core checks locally:

```bash
python -m pip install --upgrade pip
pip install pre-commit uv
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .

pre-commit run --all-files --show-diff-on-failure
```

Run the fast test subsets used in CI:

```bash
cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=. --cov-report=term-missing --cov-fail-under=80
```

```bash
cd src
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose --timeout=120 --maxfail=3
```

### Validate lockfile and docs gates

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

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### Push and monitor

After pushing your branch, monitor the `CI/CD Pipeline` run in GitHub Actions.  
If `Quality Gate` fails, treat the PR as non-mergeable until fixed.

---

## Reviewer Workflow

### What to check first

1. `Quality Gate` must be green.
2. If red, request the author resolve CI before detailed review.

### Review focus after CI passes

1. Behavior correctness for changed code paths.
2. Tests added/updated for behavior changes.
3. Lockfile updates present when dependencies changed.
4. Documentation updates for API/workflow/operator-impact changes.

### Useful reviewer checks

1. Confirm job failure context (if any) in Actions logs.
2. Verify failure is not hidden by `continue-on-error` in critical stages.
3. Confirm docs-only changes still satisfy `docs` link checks.

---

## Maintainer Workflow

### Required branch gate

Set branch protection to require `Quality Gate` from `ci.yml`.

Why:

- it aggregates all critical jobs
- it normalizes handling for conditional jobs (like integration/docker on specific events)

### Weekly maintenance

1. Review recurring failure trends in CI logs.
2. Check if lockfile failures are frequent (dependency churn signal).
3. Check docs link failures for recurring stale paths/anchors.
4. Review scheduled `security-scan.yml` output artifacts.

### Dependency update flow

Dependabot branch updates trigger `.github/workflows/lockfile-update.yml`, which:

1. compiles lockfile candidate via `uv`
2. applies to `requirements.lock`
3. commits only when changed

If CI lockfile check fails on a non-Dependabot branch, author should regenerate locally and commit:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

---

## Quality Gates And Failure Handling

### Hard gate semantics

`required-checks` fails on:

- failed `pre-commit`
- failed `unit-tests`
- failed `security`
- failed `integration-tests`
- failed `dependency-docs`
- failed `docs`
- non-success `lockfile-check`
- failed `docker-build`

### Typical triage order

1. Fix `pre-commit` failures first.
2. Fix `unit-tests` (highest signal for regressions).
3. Fix `lockfile-check` if stale.
4. Fix `docs` link issues if documentation touched.
5. Fix `docker-build` for packaging/runtime health.

---

## Common CI Failure Patterns

### 1. Stale lockfile

Symptom:

- `lockfile-check` fails with diff output

Fix:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
git add requirements.lock
```

### 2. Docs link validation failures

Symptom:

- `docs` job reports broken file/anchor links

Fix:

```bash
python scripts/check_doc_links.py --cross-repo skip
```

Then repair the exact path/anchor indicated by the script.

### 3. Test collection or marker mismatch

Symptom:

- pytest exits during collection or marker parsing

Fix:

1. Run the exact command from CI locally.
2. Validate markers in `pyproject.toml` and test files.
3. Ensure imports and test paths are stable under `cd src`.

### 4. CI-only dependency resolution differences

Symptom:

- local pass, CI import/module failure

Fix:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

---

## Operational Best Practices

1. Keep PRs scoped and avoid mixing code, dependency, and large docs rewrites when possible.
2. Update docs in the same change set when workflow behavior changes.
3. Prefer failing early and explicitly in CI jobs over implicit downstream failures.
4. Run lockfile/docs checks locally before requesting review.
5. Treat `security-scan.yml` as a maintenance signal, not just a compliance box.

---

## Related Docs

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
