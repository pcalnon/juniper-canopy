# CI/CD Quick Start

**Last Updated:** 2026-04-05  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.1  
**Status:** Current

Quick path to validate changes locally and understand what GitHub Actions will run in CI.

---

## Prerequisites

- Python `3.12+` available locally
- `pip` and `pre-commit` installed
- Repository cloned and dependencies installed

```bash
python --version
pip --version
pre-commit --version
```

---

## 1. Install Local Quality Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

CI runs `pre-commit` across Python `3.12`, `3.13`, and `3.14`, so hook failures locally will fail CI.

---

## 2. Run Fast Local Test Pass

```bash
pip install -r conf/requirements_ci.txt
pip install -e .

python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

This mirrors the CI unit/regression gate behavior and coverage threshold.

---

## 3. Trigger CI

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

`CI/CD Pipeline` runs automatically on push and PR events.

---

## 4. CI Jobs You Should Expect

Core jobs from `.github/workflows/ci.yml`:

- `Pre-commit (Python 3.12/3.13/3.14)`
- `Unit Tests + Coverage (Python 3.12/3.13/3.14)`
- `Integration Tests` (Python `3.14`)
- `Security Scans` (`gitleaks`, `bandit`, `pip-audit`)
- `Build Distribution`
- `Dependency Documentation`
- `Lockfile Freshness`
- `Documentation Links`
- `Docker Build & Smoke Test` (PR/main/develop)
- `Quality Gate`

---

## 5. Troubleshooting Fast

`pre-commit` fails:

```bash
pre-commit run --all-files
git add .
```

Coverage gate fails:

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-report=term-missing --cov-fail-under=80
```

Lockfile freshness fails:

```bash
pip install uv
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

If failures mention cross-repo links and you want visibility without failing:

```bash
python scripts/check_doc_links.py --cross-repo warn
```

---

## References

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
