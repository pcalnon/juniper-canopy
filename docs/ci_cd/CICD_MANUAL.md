# CI/CD Manual

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

Comprehensive operational guide for developers, reviewers, and maintainers working with JuniperCanopy CI workflows.

---

## Table of Contents

1. [Overview](#overview)
2. [For Developers](#for-developers)
3. [For Reviewers](#for-reviewers)
4. [For Maintainers](#for-maintainers)
5. [Workflow Deep Dive](#workflow-deep-dive)
6. [Lockfile and Dependency Workflow](#lockfile-and-dependency-workflow)
7. [Documentation Link Validation Workflow](#documentation-link-validation-workflow)
8. [Troubleshooting Playbook](#troubleshooting-playbook)

---

## Overview

JuniperCanopy CI is implemented with GitHub Actions and enforces a multi-stage quality gate:

- pre-commit checks on Python `3.12`, `3.13`, `3.14`
- unit/regression tests with coverage gate on Python `3.12`, `3.13`, `3.14`
- integration subset tests
- security scans
- build verification
- lockfile freshness verification
- documentation link verification
- Docker build and smoke test
- final aggregate quality gate

Primary workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/lockfile-update.yml`

---

## Developer Workflow

### Daily Local Workflow

1. Install/refresh development tooling.

```bash
python -m pip install --upgrade pip
pip install pre-commit uv
pre-commit install
```

2. Run the same fast unit/regression subset used by CI:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose \
  --cov=src \
  --cov-report=term-missing \
  --cov-fail-under=80
```

3. Run the same fast integration subset used by CI:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose
```

4. Run docs-link validation with CI-equivalent flags:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

5. If dependencies changed, regenerate lockfile before push:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Monitoring CI on PRs

Check the following jobs in your PR checks list:

- `Pre-commit (Python 3.12/3.13/3.14)`
- `Unit Tests + Coverage (Python 3.12/3.13/3.14)`
- `Integration Tests`
- `Security Scans`
- `Build Distribution`
- `Dependency Documentation`
- `Lockfile Freshness`
- `Documentation Links`
- `Docker Build & Smoke Test`
- `Quality Gate`

If one of these fails, treat that failure as blocking unless explicitly documented otherwise in workflow comments.

---

## For Reviewers

### Review Checklist

1. Confirm CI reached `Quality Gate` success.
2. Confirm test-related changes include corresponding test updates.
3. Confirm dependency changes include:
   - `pyproject.toml` updates
   - `requirements.lock` regeneration
   - CI lockfile-check compatibility
4. Confirm documentation changes do not break internal links.
5. Confirm no workflow drift was introduced unintentionally.

### High-Signal Failure Patterns

- `Lockfile Freshness` failed: lockfile is stale vs `pyproject.toml`.
- `Documentation Links` failed: broken markdown link or heading anchor.
- `Unit Tests + Coverage` failed at 80% threshold or test failures.
- `Docker Build & Smoke Test` failed: packaging/runtime mismatch.

---

## For Maintainers

### Operational Responsibilities

- Keep matrix and pinned runtime versions aligned across workflows.
- Keep lockfile-generation command consistent between:
  - local contributor guidance
  - CI lockfile-check job
  - lockfile-update workflow
- Ensure docs-link exclusions remain intentional and minimal.
- Periodically review artifact retention and workflow runtime cost.

### Branch Protection Guidance

Require at minimum:

- `Quality Gate`

Optionally require additional individual checks if your policy favors explicit job-level blocking.

---

## Workflow Deep Dive

### CI Trigger Model

`ci.yml` triggers on:

- `push` to `main`, `develop`, `feature/**`, `fix/**`
- `pull_request` to `main`, `develop`
- `repository_dispatch` for client update events
- manual `workflow_dispatch`

### Job Graph (Practical View)

1. `pre-commit` matrix runs first.
2. `unit-tests` matrix depends on `pre-commit`.
3. `integration-tests` and `build` depend on `unit-tests`.
4. `dependency-docs` and `docker-build` depend on `build`.
5. `security`, `lockfile-check`, and `docs` run independently.
6. `required-checks` aggregates all critical outcomes.
7. `notify` runs after `required-checks`.

### Unit Tests Special Case: Python 3.12 Exit 134

CI includes a deliberate workaround for rare Python 3.12 `SIGABRT` (`exit 134`) after pytest completion:

- If JUnit XML reports `failures=0` and `errors=0`, job exits success.
- Otherwise, CI preserves failure.

This behavior is specific to CI robustness and is implemented directly in `.github/workflows/ci.yml`.

---

## Lockfile and Dependency Workflow

### Why this exists

`requirements.lock` is the reproducibility contract for container and CI dependency resolution.

### Canonical regeneration command

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### CI freshness check behavior

CI compiles to `/tmp/requirements.lock.check`, strips first two header lines from both files, then diffs remaining content to avoid false positives caused by output-path metadata in uv headers.

### Dependabot lockfile update behavior

`lockfile-update.yml`:

- runs only for `dependabot[bot]` pushes to `dependabot/pip/**`
- compiles via `/tmp/requirements.lock.check`
- moves generated file to `requirements.lock`
- commits only when changed

---

## Documentation Link Validation Workflow

### CI command

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### What is validated

- relative markdown file links
- same-file heading anchors
- repository boundary safety for resolved paths

### Why `--cross-repo skip` in CI

CI runners do not guarantee sibling Juniper repositories on disk; cross-repo validation is skipped to avoid false negatives from absent checkouts.

---

## Troubleshooting Playbook

### `Lockfile Freshness` failed

1. Re-run canonical lockfile compile command.
2. Re-run a local body-only diff:

```bash
uv pip compile pyproject.toml --extra juniper-data --extra juniper-cascor --extra observability -o /tmp/requirements.lock.check
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
```

3. Commit updated `requirements.lock`.

### `Documentation Links` failed

Run exact CI command locally (same excludes and cross-repo policy), fix broken links/anchors, and re-run until clean.

### `Unit Tests + Coverage` failed

Run CI-equivalent unit/regression command locally and inspect:

- marker selection
- coverage threshold
- any path mismatches (`src/tests/...` expected)

### `Docker Build & Smoke Test` failed

Verify:

- `requirements.lock` is current
- package import works after `pip install -e .`
- health endpoint behavior remains stable

---

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Technical Reference](CICD_REFERENCE.md)
- [Repository README](../../README.md)
