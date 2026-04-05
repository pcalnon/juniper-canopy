# CI/CD Quick Start Guide

**Last Updated:** 2026-04-05  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0  
**Status:** Current

This guide mirrors the current GitHub Actions workflows in `.github/workflows/`.

---

## Prerequisites

- Python 3.14 available locally
- `pip` and `git` installed
- Repository cloned and dependencies installable

```bash
python --version
pip --version
git --version
```

---

## 1. Run The Same Fast Checks As CI

Install local tooling:

```bash
python -m pip install --upgrade pip
pip install pre-commit uv
pip install -r conf/requirements_ci.txt
pip install -e .
```

Run pre-commit:

```bash
pre-commit run --all-files --show-diff-on-failure
```

Run CI-equivalent fast tests:

```bash
cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=. --cov-report=term-missing
```

Run CI-equivalent fast integration tests:

```bash
cd src
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose --timeout=120 --maxfail=3
```

---

## 2. Validate Lockfile And Docs Locally

Lockfile freshness (same extras as `ci.yml` lockfile check):

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

Documentation link validation:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

---

## 3. Push And Watch CI

Push your branch:

```bash
git push origin <branch-name>
```

The `CI/CD Pipeline` workflow runs these jobs:

```text
pre-commit
unit-tests (Python 3.12, 3.13, 3.14)
integration-tests
build
security
dependency-docs
lockfile-check
docs
docker-build
required-checks
notify
```

`required-checks` is the branch gate: if it fails, merging should be blocked.

---

## 4. Quick Troubleshooting

If `unit-tests` fail only in CI, retest with Python 3.14 locally:

```bash
python -m pip install -r conf/requirements_ci.txt
pip install -e .
cd src && python -m pytest -m "not slow and not requires_server and not requires_cascor" tests/unit tests/regression -vv
```

If `lockfile-check` fails:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

If `docs` job fails:

```bash
python scripts/check_doc_links.py --cross-repo skip
```

---

## Next Docs

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
