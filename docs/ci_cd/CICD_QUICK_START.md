# CI/CD Quick Start

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0

---

## Prerequisites

- ✅ Conda environment activated (`JuniperCanopy`)
- ✅ Dependencies installed (`pip install -r conf/requirements.txt`)
- ✅ Git repository initialized
- ✅ Python 3.11+ installed (CI matrix currently validates 3.12, 3.13, 3.14)

**Verify:**

```bash
python --version      # Should be 3.11+
pytest --version      # Should be 7.0+
conda env list | grep JuniperCanopy  # Should show active
```

## 1. Install Local Quality Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

**3. Verify:**

```bash
pre-commit --version  # Output: pre-commit 3.x.x
```

---

## Run Tests Locally

**Quick test:**

```bash
python -m pytest src/tests/ -v
```

**With coverage:**

```bash
python -m pytest src/tests/ --cov=src --cov-report=term-missing
```

**Expected output:**

```bash

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
CI/CD Pipeline
├── ✓ Pre-commit (Python 3.12/3.13/3.14)
├── ✓ Unit Tests + Coverage (Python 3.12/3.13/3.14)
├── ✓ Integration Tests
├── ✓ Security Scans
├── ✓ Build Distribution
├── ✓ Dependency Documentation
├── ✓ Lockfile Freshness
├── ✓ Documentation Links
├── ✓ Docker Build & Smoke Test
├── ✓ Quality Gate
└── ✓ Build Notification
```

**3. Download artifacts:**

- Scroll to bottom
- Download test results and coverage reports

---

## Next Steps

### Add Coverage Badge

Use a project-supported coverage source (for example, a generated static badge or a GitHub artifact summary) if you want a badge in `README.md`.

Commit `requirements.lock` when it changes.

- Settings → Branches → Add rule
- ☑ Require pull request reviews
- ☑ Require status checks (`Quality Gate`)
- ☑ Require branches up to date

CI runs `scripts/check_doc_links.py` and fails on broken internal links.

```bash
# Pre-commit
pre-commit run --all-files

# Tests
python -m pytest src/tests/unit/test_demo_mode.py -v

# Coverage
python -m pytest src/tests/ --cov=src --cov-report=html:reports/htmlcov
xdg-open reports/htmlcov/index.html

# Documentation link checks (same validator used in CI)
python scripts/check_doc_links.py --cross-repo skip

# Lockfile refresh (after dependency changes)
uv pip compile pyproject.toml --extra juniper-data --extra juniper-cascor --extra observability -o requirements.lock

# Formatting
black src/ --line-length=120
isort src/ --profile=black
```

## 5. Understand CI Job Flow

Current `CI/CD Pipeline` jobs:

```bash
black src/ --line-length=120
isort src/ --profile=black
git add .
git commit -m "Apply formatting"
```

### Tests fail locally

```bash
conda activate JuniperCanopy
pip install -r conf/requirements.txt
python -m pytest src/tests/unit/test_demo_mode.py::test_name -vv
```

## 6. Troubleshooting Fast

```bash
# Test with CI Python version
conda create -n test-py314 python=3.14
conda activate test-py314
pip install -r conf/requirements.txt
python -m pytest src/tests/ -v
```

Install exactly from `conf/requirements_ci.txt` and `pip install -e .`.

### Lockfile check fails

Regenerate `requirements.lock` using the exact compile command shown above.

### Docs check fails

Run `scripts/check_doc_links.py` locally and fix the broken path/anchor.

✅ Installed pre-commit hooks  
✅ Ran tests with coverage  
✅ Made first CI/CD commit  
✅ Viewed CI results

**CI/CD is active!** Every push triggers quality checks, tests, and artifact publication.

## Next Reads

- [CI/CD Manual](CICD_MANUAL.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Technical Reference](CICD_REFERENCE.md)
