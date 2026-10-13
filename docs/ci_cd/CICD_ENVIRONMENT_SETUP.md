# CI/CD Environment Setup

**Last Updated:** 2026-10-08
**Version:** 0.28.1
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
- `.github/workflows/claude.yml` (optional assistant; not a merge gate)

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

Core install pattern (the `unit-tests` job; the other jobs install their own extras sets):

```bash
python -m pip install --upgrade "pip>=26.1.1"
if [ "$RUNNER_OS" = "macOS" ]; then
  pip install torch
else
  pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
pip install -e ".[test,juniper-cascor,observability]"
pip install "h5py>=3.0"
```

Why this matters:

- `torch` is installed before the project extras because wheel resolution differs by runner OS.
- Linux installs CPU-only torch from the PyTorch CPU index to avoid CUDA wheels.
- macOS installs torch from the default PyPI index because the Linux CPU-only index has no macOS ARM wheels.
- The editable install (`-e`) ensures imports resolve the current source tree.
- Repo-root `requirements.txt` resolves to `conf/requirements_ci.txt` (`requirements.txt` → `conf/requirements.txt` → `conf/requirements_ci.txt`). Dependabot's pip updates (`directory: "/"`) commit floor bumps in that file. No `ci.yml` job installs it: since canopy#650 it is `juniper-generate-dep-docs` output, and every lane installs `pyproject.toml` extras instead.
- `requirements.lock` is compiled from `pyproject.toml`. A floor that exists only in `conf/requirements_ci.txt` can change while that package stays out of the lock. Reviewer notes: [Dependabot lockfile automation](CICD_MANUAL.md#runbook-dependabot-lockfile-automation).
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
- `ANTHROPIC_API_KEY`:
  Read by `claude.yml` as the only auth input (`anthropic_api_key`). The workflow header says this is an org secret and that the repo must be able to read it. Bedrock, Vertex, Foundry, and workload-identity inputs are not set.

### Workflow permissions

- `ci.yml`: `contents: read` globally, with `security-events: write` in the security job for Bandit SARIF upload (`github/codeql-action/upload-sarif`, SHA-pinned with the CodeQL family)
- `codeql.yml`: `actions: read`, `contents: read`, `security-events: write` for CodeQL analyze
- `publish.yml`: `id-token: write` for OIDC trusted publishing
- `lockfile-update.yml`: `contents: write` for bot lockfile commits
- `claude.yml`: `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: read`. Not a required check. `id-token: write` is granted even though the workload-identity inputs are unset.

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

Dependabot branches also trigger `.github/workflows/lockfile-update.yml`, which compiles `pyproject.toml` with the same extras and `--upgrade`.
It does not compile `conf/requirements_ci.txt`. A green run can commit pin moves for packages the floor bump did not name,
and the bumped package stays out of `requirements.lock` when it is not a `pyproject.toml` dependency.
An empty `CROSS_REPO_DISPATCH_TOKEN` in the Dependabot secret store skips that regen and still leaves this job green.
See [Dependabot lockfile automation](CICD_MANUAL.md#runbook-dependabot-lockfile-automation).

### `Documentation Links` fails unexpectedly

Run the exact command from the workflow and inspect the reported file/anchor path.

### Matrix-only failures (for example Python 3.12)

Reproduce with that interpreter locally and run the same marker filters used in `ci.yml`.

### `Analyze (python)` is red after a GitHub Actions bump

Confirm `.github/workflows/codeql.yml` and the `ci.yml` `upload-sarif` step share the same `github/codeql-action` SHA comment. Dependabot groups those uses; splitting the pins is the usual review mistake.

### `@claude` did not call the model

The job in `.github/workflows/claude.yml` starts only for `@claude` on a new comment, a submitted review body, or an issue being opened or assigned (title or body).
GitHub's `contains()` ignores case, so `@Claude` starts it too. A pull-request description does not match.
If the job starts and the step logs `No trigger found, skipping remaining steps`, the action's own check did not find `@claude` as a separate word.
Assigning an issue always ends this way, because `assignee_trigger` is unset and the action does not re-read the title or body on `assigned`.
A bot that does match fails the step; `allowed_bots` is empty. Then confirm `ANTHROPIC_API_KEY` is visible to the repo.
Full contract: [Claude Code workflow](CICD_REFERENCE.md#claude-code-workflow).

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
