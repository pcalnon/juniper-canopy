# CI/CD Environment Setup

**Last Updated:** 2026-08-24
**Version:** 0.28.0
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
- `.github/workflows/codeql.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/lockfile-update.yml`

## Runner and Python Strategy

- Matrix jobs (`pre-commit`, `unit-tests`): Ubuntu Python `3.12`, `3.13`, `3.14`; unit tests also run on required macOS Python `3.12`
- Single-version jobs (`integration-tests`, `build`, `security`, `docs`, `lockfile-check`, `dependency-docs`): Python `3.14`
- `actions/setup-python` with `cache: pip` is used across jobs

Example from `ci.yml`:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest]
    python-version: ["3.12", "3.13", "3.14"]
    include:
      - os: macos-latest
        python-version: "3.12"
        experimental: false
```

## Dependency Installation Model

### CI jobs (`ci.yml`)

Core install pattern:

```bash
python -m pip install --upgrade pip
if [ "$RUNNER_OS" = "macOS" ]; then
  pip install torch
else
  pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
pip install -r conf/requirements_ci.txt
pip install -e .
```

Why this matters:

- `torch` is installed before `conf/requirements_ci.txt` because wheel resolution differs by runner OS.
- Linux installs CPU-only torch from the PyTorch CPU index to avoid CUDA wheels.
- macOS installs torch from the default PyPI index because the Linux CPU-only index has no macOS ARM wheels.
- `pip install -e .` ensures imports resolve the current source tree.
- `conf/requirements_ci.txt` is the CI baseline, not `requirements.txt`; dependency PRs may bump minimum versions there when the CI floor changes.
- `conf/requirements_ci.txt` includes `prometheus-client` and `sentry-sdk` used by observability paths.

## CI Environment Variables

Top-level env values in `ci.yml`:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  --constraint requirements.lock \
  -o /tmp/requirements.lock.check
```

The freshness check resolves with `requirements.lock` as a constraint, then compares package pin lines only. It fails when the committed lockfile no longer satisfies `pyproject.toml`, not merely because newer package versions exist.

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

- `ci.yml`: `contents: read` globally, with `security-events: write` in the security job for Bandit SARIF upload (`github/codeql-action/upload-sarif`, SHA-pinned with the CodeQL family)
- `codeql.yml`: `actions: read`, `contents: read`, `security-events: write` for CodeQL analyze
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
  --constraint requirements.lock \
  -o /tmp/requirements.lock.check
```

The check compares resolved package pins only, ignoring comments and generated header paths so `uv` annotations and `/tmp` output paths do not create false failures.

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
  --upgrade \
  -o requirements.lock
```

Dependabot branches also trigger `.github/workflows/lockfile-update.yml`, which runs the same extras with `--upgrade` and commits `requirements.lock` only when the resolved pins change.

### `Documentation Links` fails unexpectedly

Run the exact command from the workflow and inspect the reported file/anchor path.

### Matrix-only failures (for example Python 3.12)

Reproduce with that interpreter locally and run the same marker filters used in `ci.yml`.

### `Analyze (python)` is red after a GitHub Actions bump

Confirm `.github/workflows/codeql.yml` and the `ci.yml` `upload-sarif` step share the same `github/codeql-action` SHA comment. Dependabot groups those uses; splitting the pins is the usual review mistake.

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
