# CI/CD Quick Start

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0  
**Status:** Current

---

## Prerequisites

- Python `3.14` available locally (recommended for workflow parity)
- `pip` and `git` installed
- Repository checked out

Verify:

```bash
python --version
git --version
```

---

## 1. Install Local Quality Tooling

```bash
# From repo root
python -m pip install --upgrade pip
pip install pre-commit
pre-commit install
```

Run all hooks once:

```bash
pre-commit run --all-files
```

Notes:

- Documentation linting excludes `CHANGELOG.md`, `docs/history/`, and `notes/*_HEADER.md` templates.
- CI uses the same pre-commit configuration.

---

## 2. Run CI-Parity Unit Tests Locally

From repo root:

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

This mirrors the `unit-tests` job behavior in `.github/workflows/ci.yml`.

---

## 3. Run Fast Integration Subset

```bash
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  src/tests/integration \
  --verbose \
  --timeout=120 \
  --maxfail=3
```

---

## 4. Validate Lockfile Freshness

Install `uv` and compare lockfile body exactly as CI does:

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

If diff is non-empty, regenerate:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

---

## 5. Validate Documentation Links

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

Why `--cross-repo skip` in CI:

- CI runners usually do not have sibling Juniper repositories checked out.
- Internal in-repo links still fail the job if broken.

---

## 6. Push and Monitor Required Checks

Push your branch and watch GitHub Actions checks:

```bash
git push -u origin <branch-name>
```

Required quality gate inputs:

- `pre-commit`
- `unit-tests`
- `integration-tests`
- `security`
- `build`
- `dependency-docs`
- `lockfile-check`
- `docs`
- `docker-build`

---

## Optional: Testing Extras for Service-Mode Suites

Some tests intentionally skip unless client testing extras are installed.

```bash
pip install "juniper-cascor-client[testing]" "juniper-data-client[testing]"
```

These extras are required for tests importing:

- `juniper_cascor_client.testing`
- `juniper_data_client.testing`

---

## Next Steps

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)

