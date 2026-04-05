# CI/CD Manual

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

- [Overview](#overview)
- [Pipeline Intent and Architecture](#pipeline-intent-and-architecture)
- [Developer Workflow](#developer-workflow)
- [Maintainer Runbooks](#maintainer-runbooks)
- [Quality Gates and Merge Criteria](#quality-gates-and-merge-criteria)
- [Troubleshooting by Failing Job](#troubleshooting-by-failing-job)

## Overview

This manual describes how the current GitHub Actions pipeline works and how to operate it safely.
It is source-verified against:

- `.github/workflows/ci.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/lockfile-update.yml`
- `.github/workflows/publish.yml`
- `pyproject.toml`
- `scripts/check_doc_links.py`

## Pipeline Intent and Architecture

The pipeline enforces three outcomes:

- Code quality and test safety (`pre-commit`, `unit-tests`, `integration-tests`)
- Supply-chain and security hygiene (`security`, lockfile, scheduled scan)
- Operational correctness of artifacts and docs (`build`, `docker-build`, `docs`, `dependency-docs`)

Primary workflow (`ci.yml`) flow:

1. `pre-commit` runs on Python `3.12/3.13/3.14`
2. `unit-tests` runs matrix tests with coverage gate (`--cov-fail-under=80`)
3. `build` runs once on Python `3.14`
4. Parallel validation jobs run:
   - `integration-tests`
   - `security`
   - `dependency-docs`
   - `lockfile-check`
   - `docs`
   - `docker-build`
5. `required-checks` aggregates results and blocks on failures
6. `notify` emits final summary

## Developer Workflow

### 1. Before pushing a branch

```bash
pre-commit run --all-files

cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose \
  --cov=. \
  --cov-report=term-missing
```

For integration-sensitive changes:

```bash
cd src
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose
```

### 2. If dependencies changed

Regenerate lockfile exactly as CI expects:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### 3. If docs changed

Validate links with CI-equivalent arguments:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## Maintainer Runbooks

### Runbook: Dependabot lockfile automation

When Dependabot pushes to `dependabot/pip/**`, `lockfile-update.yml`:

1. Regenerates `requirements.lock` via `uv pip compile`
2. Commits `[dependabot skip] Update requirements.lock` if changed
3. Pushes with `CROSS_REPO_DISPATCH_TOKEN` so downstream CI is triggered

Operational constraints:

- Keep `CROSS_REPO_DISPATCH_TOKEN` valid
- Keep compile extras aligned with `ci.yml` (`juniper-data`, `juniper-cascor`, `observability`)
- Keep `requirements.lock` committed in PRs that modify dependency constraints

### Runbook: Scheduled security scan

`security-scan.yml` runs weekly and manually:

1. Installs `bandit[sarif]`, `pip-audit`, and project package (`pip install -e .`)
2. Runs Bandit with SARIF output and text output
3. Runs `pip-audit --strict --desc on`
4. Uploads `reports/security/` artifacts

Use this runbook after dependency updates to confirm no new vulnerabilities are introduced.

### Runbook: Release publishing

`publish.yml` is release-triggered (`release: published`) and uses OIDC:

1. Build and `twine check`
2. Publish to TestPyPI (`environment: testpypi`)
3. Verify installation from TestPyPI
4. Publish to PyPI (`environment: pypi`)

Do not bypass TestPyPI stage; production publish is intentionally downstream.

## Quality Gates and Merge Criteria

PRs are merge-safe when `Quality Gate` succeeds.

`required-checks` enforces:

- Must succeed:
  - `pre-commit`
  - `unit-tests`
  - `lockfile-check`
- Must not fail:
  - `integration-tests` (allowed skipped outside configured refs)
  - `security`
  - `docs`
  - `dependency-docs` (skipped acceptable, failure not)
  - `docker-build` (skipped acceptable, failure not)

Coverage policy:

- Unit-test matrix uses `--cov-fail-under=80` from workflow env and pytest command line.

## Troubleshooting by Failing Job

### `unit-tests` failing on one Python version only

- Reproduce with that interpreter locally.
- Confirm dependency compatibility with `conf/requirements_ci.txt`.
- Re-run marker-filtered command from this manual.

### `lockfile-check` fails with diff

- Recompile `requirements.lock` using all three extras.
- Ensure no manual edits were made to lockfile body.

### `docs` fails

- Run `scripts/check_doc_links.py` with workflow excludes and `--cross-repo skip`.
- Fix broken relative paths or heading anchors.

### `dependency-docs` fails

- Re-run `scripts/generate_dep_docs.sh` locally.
- Validate `conf/conda_environment_ci.yaml` parses and contains dependencies.

### `docker-build` fails

- Build local image from root `Dockerfile`.
- Start container and verify `/v1/health` response.
- Check image startup logs for import/config errors.

### `security` fails

- For Bandit: review `reports/security/bandit.txt` and prioritize medium/high findings.
- For pip-audit: update vulnerable dependencies and regenerate lockfile.

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [Testing Manual](../testing/TESTING_MANUAL.md)
