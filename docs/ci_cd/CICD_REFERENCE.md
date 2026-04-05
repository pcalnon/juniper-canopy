# CI/CD Technical Reference

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

Technical reference aligned with active workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/lockfile-update.yml`

---

## Table of Contents

1. [Workflow Inventory](#workflow-inventory)
2. [Main Pipeline (`ci.yml`)](#main-pipeline-ciyml)
3. [Security Workflow (`security-scan.yml`)](#security-workflow-security-scanyml)
4. [Publish Workflow (`publish.yml`)](#publish-workflow-publishyml)
5. [Dependabot Lockfile Workflow (`lockfile-update.yml`)](#dependabot-lockfile-workflow-lockfile-updateyml)
6. [CI Scripts And Inputs](#ci-scripts-and-inputs)
7. [Branch Protection And Required Checks](#branch-protection-and-required-checks)

---

## Workflow Inventory

| Workflow File | Primary Purpose | Trigger |
| ------------- | --------------- | ------- |
| `ci.yml` | Main quality gate for pushes/PRs | push, pull_request, repository_dispatch, workflow_dispatch |
| `security-scan.yml` | Scheduled and on-demand security scanning | schedule (weekly), workflow_dispatch |
| `publish.yml` | Release publishing to TestPyPI and PyPI | release published |
| `lockfile-update.yml` | Dependabot lockfile regeneration | push to `dependabot/pip/**` by Dependabot |

---

## Main Pipeline `ci.yml`

### Global Settings

- Concurrency group: `ci-${{ github.ref }}`
- Coverage gate env: `COVERAGE_FAIL_UNDER=80`
- Default high-use Python in non-matrix jobs: `PYTHON_TEST_VERSION=3.14`

### Job Matrix

`pre-commit` and `unit-tests` run matrix Python:

- `3.12`
- `3.13`
- `3.14`

Other jobs use `3.14` unless otherwise noted.

### Job List

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

### Test Selection Rules

Unit/regression fast subset:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/
```

Integration fast subset:

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration
```

### Lockfile Freshness Check

`lockfile-check` compiles to `/tmp/requirements.lock.check` with extras:

- `juniper-data`
- `juniper-cascor`
- `observability`

and then diffs against `requirements.lock`.

### Documentation Link Check

`docs` job runs:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### Required Checks Semantics

`required-checks` is the gatekeeper and fails when:

- `pre-commit` is not `success`
- `unit-tests` is not `success`
- `integration-tests` is `failure`
- `security` is `failure`
- `dependency-docs` is `failure`
- `docs` is `failure`
- `lockfile-check` is not `success`
- `docker-build` is `failure`

---

## Security Workflow `security-scan.yml`

### Trigger

- Weekly cron: Monday 06:00 UTC
- Manual dispatch

### Steps

1. Checkout
2. Setup Python `3.14`
3. Install `bandit[sarif]`, `pip-audit`, project dev extras
4. Run Bandit SARIF + medium confidence/severity scan
5. Run strict `pip-audit`
6. Upload `reports/security/` artifacts

### Operational Note

This is complementary to the `security` job in `ci.yml`; it is not a replacement.

---

## Publish Workflow `publish.yml`

### Trigger

- GitHub release published

### Jobs

1. `build`
2. `testpypi`
3. `pypi`

### Flow

1. Build sdist/wheel and run `twine check`
2. Publish artifacts to TestPyPI via trusted publishing
3. Verify install from TestPyPI
4. Publish to PyPI via trusted publishing

### Auth Model

- OIDC trusted publishing
- `permissions: id-token: write`

No long-lived PyPI API token should be required for this workflow.

---

## Dependabot Lockfile Workflow `lockfile-update.yml`

### Trigger Condition

- Branch: `dependabot/pip/**`
- Actor: `dependabot[bot]`

### Core Behavior

1. Checkout with `CROSS_REPO_DISPATCH_TOKEN`
2. Setup Python `3.14`
3. Install `uv`
4. Compile lockfile candidate to `/tmp/requirements.lock.check`
5. Move candidate to `requirements.lock`
6. Commit and push only if changed

### Compile Command

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
mv /tmp/requirements.lock.check requirements.lock
```

---

## CI Scripts And Inputs

### `scripts/check_doc_links.py`

Purpose:

- validates internal markdown file links and heading anchors
- supports cross-repo policies: `skip`, `warn`, `check`

CI uses `--cross-repo skip` for deterministic execution in isolated runners.

### `scripts/generate_dep_docs.sh`

Used by `dependency-docs` job to regenerate:

- `conf/requirements_ci_*.txt`
- `conf/conda_environment_ci*.yaml` artifacts

---

## Branch Protection And Required Checks

For branch protection, prefer requiring at least:

1. `Quality Gate` (the `required-checks` job)
2. `Documentation Links` (if exposed separately in your repo settings view)

If only one check is required, use `Quality Gate` because it aggregates all critical jobs.
