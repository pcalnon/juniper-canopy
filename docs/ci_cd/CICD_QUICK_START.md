# CI/CD Quick Start Guide

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0

## Prerequisites

- Python 3.14 locally (matches CI default jobs)
- `pip` available
- Git repository checked out

Verify:

```bash
python --version
pip --version
git status --short --branch
```

## 1. Install CI-equivalent dependencies

```bash
pip install -r conf/requirements_ci.txt
pip install -e .
```

Notes:
- CI also installs CPU-only `torch` from the PyTorch CPU index.
- `conf/requirements_ci.txt` includes observability/runtime deps used in CI (`prometheus-client`, `sentry-sdk`).

## 2. Run the same core checks as CI

Run from repo root unless noted.

```bash
# Code quality hooks
pre-commit run --all-files

# Fast unit + regression subset with coverage gate (same marker strategy as CI)
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src \
  --cov-report=term-missing \
  --cov-fail-under=80

# Fast integration subset
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration
```

## 3. Validate documentation links locally

The CI `docs` job runs `scripts/check_doc_links.py` with cross-repo checks skipped.

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## 4. Keep `requirements.lock` fresh

CI compares a regenerated lockfile body (header-stripped) against `requirements.lock`.

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

## 5. Know what CI runs on PRs

`CI/CD Pipeline` jobs:

- `Pre-commit (Python 3.12/3.13/3.14)`
- `Unit Tests + Coverage (Python 3.12/3.13/3.14)`
- `Integration Tests` (fast subset)
- `Build Distribution`
- `Security Scans`
- `Dependency Documentation`
- `Lockfile Freshness`
- `Documentation Links`
- `Docker Build & Smoke Test`
- `Quality Gate`

## Common Pitfalls

- Optional client testing modules are intentionally skipped when extras are not installed:
  - `juniper_cascor_client.testing`
  - `juniper_data_client.testing`
- A Python 3.12 `pytest` cleanup SIGABRT (`exit 134`) is handled in CI by checking JUnit failures/errors before failing the job.
- Link checker failures are often from moved docs paths or broken anchors, not runtime code.

## Next Steps

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
