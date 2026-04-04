# CI/CD Quick Start Guide

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.26.0

---

## Prerequisites

- ✅ Python 3.12+ available
- ✅ Virtual environment or conda environment activated
- ✅ Dependencies installed (`pip install -r conf/requirements_ci.txt`)
- ✅ Git repository initialized

**Verify:**

```bash
python --version      # Should be 3.12+
pytest --version      # Should be 7.0+
pip --version
```

---

## Install Pre-commit Hooks

**1. Install pre-commit:**

```bash
pip install pre-commit
```

**2. Install hooks:**

```bash
pre-commit install
```

**3. Verify:**

```bash
pre-commit --version  # Output: pre-commit 3.x.x
```

---

## Run Tests Locally

**Quick test:**

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose
```

**With coverage:**

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --cov=src --cov-report=term-missing \
  --cov-fail-under=80
```

**Expected output:**

```bash
============================= test session starts =============================
...
============================== 320 passed in XXs ==============================
...
TOTAL                                         ...                        80%+
```

**View HTML report:**
<file:///home/pcalnon/Development/python/Juniper/juniper-canopy/src/tests/reports/coverage/index.html>

---

## Set Up GitHub Secrets

**1. Generate Codecov token:**

- Go to [codecov.io](https://codecov.io)
- Sign in with GitHub
- Add repository
- Copy upload token

**2. Add to GitHub:**

- Repository → **Settings** → **Secrets and variables** → **Actions**
- Click **New repository secret**
- Name: `CODECOV_TOKEN`
- Value: Paste token
- Click **Add secret**

---

## Make Your First Commit

**1. Stage changes:**

```bash
git add src/config_manager.py
```

**2. Commit (hooks run automatically):**

```bash
git commit -m "Update configuration handling"
```

**Pre-commit runs:**

```bash
Trim Trailing Whitespace.............................Passed
Fix End of Files.....................................Passed
Check Yaml...........................................Passed
black................................................Passed
isort................................................Passed
flake8...............................................Passed
```

**3. Push:**

```bash
git push origin feature/your-branch
```

---

## View CI Results

**1. Go to GitHub:**

- Actions tab
- See "CI/CD Pipeline" running

**2. Jobs:**

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
└── ✓ Quality Gate

Total: ~10-15 minutes (parallel jobs)
```

**3. Download artifacts:**

- Scroll to bottom
- Download test results and coverage reports

---

## Next Steps

### Add Coverage Badge

```markdown
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
```

### Enable Branch Protection

- Settings → Branches → Add rule
- ☑ Require pull request reviews
- ☑ Require status checks (Quality Gate)
- ☑ Require branches up to date

### Validate Docs and Lockfile Locally

```bash
# Check documentation links (same exclusions as CI)
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip

# Regenerate lockfile after dependency changes
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

---

## Common Commands

```bash
# Pre-commit
pre-commit run --all-files

# Tests
pytest tests/unit/test_demo_mode.py -v

# Coverage
cd src && pytest tests/ --cov=. --cov-report=html
open ../reports/coverage/index.html

# Formatting
black src/ --line-length=120
isort src/ --profile=black
```

---

## Troubleshooting

### Pre-commit fails

```bash
black src/ --line-length=120
isort src/ --profile=black
git add .
git commit -m "Apply formatting"
```

### Tests fail locally

```bash
python -m venv .venv-ci
# activate .venv-ci for your shell, then:
pip install -r conf/requirements_ci.txt
python -m pytest src/tests/unit/test_demo_mode.py::test_name -vv
```

### CI fails but local passes

```bash
# Test with CI Python versions
for ver in 3.12 3.13 3.14; do
  python -m venv ".venv-$ver"
  # activate env per shell, then:
  pip install -r conf/requirements_ci.txt
  python -m pytest -m "not requires_cascor and not requires_server and not slow" src/tests/unit/ src/tests/regression/
done
```

---

## Resources

- [CI/CD Manual](CICD_MANUAL.md) - Complete guide
- [Environment Setup](CICD_ENVIRONMENT_SETUP.md) - Configuration
- [Reference](CICD_REFERENCE.md) - Technical specs
- [AGENTS.md](../../AGENTS.md) - Project development guide
- [README.md](../../README.md) - Project overview

---

**You've completed:**

✅ Installed pre-commit hooks  
✅ Ran tests with coverage  
✅ Set up Codecov  
✅ Made first CI/CD commit  
✅ Viewed CI results

**CI/CD is active!** Every push triggers quality checks, tests, and coverage reporting.

---

**Status:** ✅ Ready to use
