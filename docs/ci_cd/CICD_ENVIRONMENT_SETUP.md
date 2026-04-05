# CI/CD Environment Setup

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

- [Overview](#overview)
- [Runner and Python Strategy](#runner-and-python-strategy)
- [Dependency Installation Model](#dependency-installation-model)
- [Secrets and Permissions](#secrets-and-permissions)
- [Quality Gates That Depend on Environment](#quality-gates-that-depend-on-environment)
- [Troubleshooting](#troubleshooting)

## Overview

This project's CI runs on GitHub-hosted `ubuntu-latest` runners with a pip-first setup.  
The workflow definitions are:

- `.github/workflows/ci.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/lockfile-update.yml`

## Runner and Python Strategy

- Matrix jobs (`pre-commit`, `unit-tests`): Python `3.12`, `3.13`, `3.14`
- Single-version jobs (`integration-tests`, `build`, `security`, `docs`, `lockfile-check`, `dependency-docs`): Python `3.14`
- `actions/setup-python` with `cache: pip` is used across jobs

Example from `ci.yml`:

```yaml
strategy:
  matrix:
    python-version: ["3.12", "3.13", "3.14"]
```

## Dependency Installation Model

### CI jobs (`ci.yml`)

Core install pattern:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Why this matters:

- `torch` is installed from the CPU index explicitly for runner compatibility.
- `pip install -e .` ensures imports resolve the current source tree.
- `conf/requirements_ci.txt` is the CI baseline, not `requirements.txt`.

### Scheduled security scan (`security-scan.yml`)

Security workflow installs scanning tools and project dependencies with:

```bash
pip install "bandit[sarif]" pip-audit
pip install -e .
```

## Secrets and Permissions

### Required secrets

- `CROSS_REPO_DISPATCH_TOKEN`:
  Used by `lockfile-update.yml` to push lockfile updates in Dependabot branches with CI retriggering behavior.

### Workflow permissions

- `ci.yml`: `contents: read` globally, with `security-events: write` in the security job for SARIF upload
- `publish.yml`: `id-token: write` for OIDC trusted publishing
- `lockfile-update.yml`: `contents: write` for bot lockfile commits

## Quality Gates That Depend on Environment

### Lockfile Freshness

`ci.yml` validates that `requirements.lock` matches `pyproject.toml` with:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
```

The check strips generated header lines before diffing so output path differences do not create false failures.

### Documentation Links

`ci.yml` runs:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

`--cross-repo skip` is required for isolated CI runners that do not checkout sibling ecosystem repositories.

## Troubleshooting

### `Lockfile Freshness` fails after dependency changes

Regenerate locally with the same extras:

```bash
pip install uv
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### `Documentation Links` fails unexpectedly

Run the exact command from the workflow and inspect the reported file/anchor path.

### Matrix-only failures (for example Python 3.12)

Reproduce with that interpreter locally and run the same marker filters used in `ci.yml`.

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
