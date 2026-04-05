# CI/CD Quick Start

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0  
**Status:** Current

## Prerequisites

- Python `3.12+` available locally
- Git repository clone is up to date
- `pip` and `pre-commit` installed
- Optional: `uv` for lockfile checks

## 1. Run Local CI-Parity Checks

```bash
# From repo root
python -m pip install --upgrade pip
pip install pre-commit
pre-commit run --all-files
```

## 2. Run Fast Unit + Regression Subset

```bash
mkdir -p logs src/logs reports/junit reports/htmlcov
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=reports/junit/junit-unit.xml \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

## 3. Run Fast Integration Subset

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose \
  --timeout=120 \
  --maxfail=3 \
  --junitxml=reports/junit/junit-integration.xml
```

## 4. Validate Documentation Links

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## 5. Verify Lockfile Freshness

```bash
pip install uv
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
tail -n +3 requirements.lock > /tmp/lock_body
tail -n +3 /tmp/requirements.lock.check > /tmp/check_body
diff -u /tmp/lock_body /tmp/check_body
```

## Current CI Jobs (High-Level)

- `pre-commit`: quality hooks on Python `3.12`, `3.13`, `3.14`
- `unit-tests`: unit + regression tests with `80%` coverage gate
- `integration-tests`: fast integration marker subset
- `build`: sdist/wheel packaging validation
- `security`: gitleaks + bandit + pip-audit
- `dependency-docs`: dependency snapshot generation
- `lockfile-check`: `requirements.lock` freshness
- `docs`: markdown link validation
- `docker-build`: container build + smoke test
- `required-checks`: aggregate quality gate

## Common Failure Fixes

### Optional testing extras missing

Some integration/unit tests intentionally skip unless extras are installed:

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

### `requirements.lock` stale

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Docs link validation fails

Run the same validator locally and fix reported file/anchor paths:

```bash
python scripts/check_doc_links.py --cross-repo skip
```

## Next Steps

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
