# CI/CD Quick Start

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0  
**Status:** Current

## Prerequisites

- Python 3.12+ available locally
- `pip` and `git` installed
- Repository cloned

```bash
python --version
pip --version
git --version
```

## 1. Install Local Quality Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

This mirrors the `pre-commit` job in `.github/workflows/ci.yml`.

## 2. Run the Same Fast Tests as CI

From repository root:

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
mkdir -p logs src/logs reports/junit reports/coverage reports/htmlcov
```

Run CI-equivalent unit and regression tests:

```bash
CASCOR_BACKEND_AVAILABLE=0 RUN_SERVER_TESTS=0 ENABLE_SLOW_TESTS=0 \
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=src --cov-report=term-missing
```

Coverage gate in CI is `80%` (`COVERAGE_FAIL_UNDER` in `ci.yml`).

## 3. Validate Lockfile Freshness

CI fails when `requirements.lock` does not match `pyproject.toml` (+ extras).

```bash
pip install uv
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

Commit `requirements.lock` when it changes.

## 4. Validate Documentation Links

CI runs `scripts/check_doc_links.py` and fails on broken internal links.

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## 5. Understand CI Job Flow

Current `CI/CD Pipeline` jobs:

1. `pre-commit` (Python 3.12, 3.13, 3.14)
2. `unit-tests` (Python matrix + coverage gate)
3. `integration-tests` (PR/main/develop only)
4. `build`
5. `security`
6. `dependency-docs`
7. `lockfile-check`
8. `docs` (link validation)
9. `docker-build` (PR/main/develop only)
10. `required-checks`
11. `notify`

## 6. Troubleshooting Fast

### Collection/import failures in CI

Install exactly from `conf/requirements_ci.txt` and `pip install -e .`.

### Lockfile check fails

Regenerate `requirements.lock` using the exact compile command shown above.

### Docs check fails

Run `scripts/check_doc_links.py` locally and fix the broken path/anchor.

### Python version mismatch issues

Reproduce with Python 3.14 locally (primary CI runtime for non-matrix jobs).

## Next Reads

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Technical Reference](CICD_REFERENCE.md)
