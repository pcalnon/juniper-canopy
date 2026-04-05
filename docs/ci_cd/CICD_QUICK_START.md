# CI/CD Quick Start Guide

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5-10 minutes  
**Version:** 0.26.0

---

## Prerequisites

- Python 3.12+ available locally
- Project dependencies installable from `conf/requirements_ci.txt`
- `uv` installed for lockfile checks
- Repository root as current working directory

```bash
python --version
python -m pip --version
pytest --version
uv --version
```

---

## 1. Install CI-Parity Dependencies

```bash
python -m pip install --upgrade pip
pip install -r conf/requirements_ci.txt
pip install -e .
```

Why: CI jobs run with `conf/requirements_ci.txt` plus editable install. This includes observability packages such as `sentry-sdk` and `prometheus-client`, which are required for test collection.

---

## 2. Run Local Checks Matching CI

Run these from repo root (not `src/`). Running from root keeps coverage omit patterns aligned with `pyproject.toml`.

### Pre-commit

```bash
pre-commit run --all-files
```

### Unit + Regression (coverage gate)

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose \
  --timeout=60 \
  --maxfail=5 \
  --cov=src \
  --cov-report=term-missing \
  --cov-fail-under=80
```

### Integration (fast subset)

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose \
  --timeout=120 \
  --maxfail=3
```

---

## 3. Validate Lockfile Freshness

`CI` validates `requirements.lock` using all extras, including observability:

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

If stale, regenerate:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

---

## 4. Validate Documentation Links

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

This matches the `docs` job in `.github/workflows/ci.yml`.

---

## 5. Confirm Workflow Jobs

Current `CI/CD Pipeline` jobs:

- `pre-commit`
- `unit-tests` (Python 3.12/3.13/3.14)
- `integration-tests`
- `build`
- `security`
- `dependency-docs`
- `lockfile-check`
- `docs`
- `docker-build`
- `required-checks`
- `notify`

---

## Common Pitfalls

### `ModuleNotFoundError: sentry_sdk` or `prometheus_client`

Install CI requirements (not just runtime requirements):

```bash
pip install -r conf/requirements_ci.txt
```

### Coverage unexpectedly includes test files

Run pytest from repository root and target `src/tests/...` paths as shown above.

### Lockfile check fails even after compile

Ensure `--extra observability` is included in the compile command.

### Docs job fails locally

Use the same exclusions and `--cross-repo skip` mode as CI.

---

## Resources

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Technical Reference](CICD_REFERENCE.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [Workflow Source](../../.github/workflows/ci.yml)
- [Link Checker Script](../../scripts/check_doc_links.py)
