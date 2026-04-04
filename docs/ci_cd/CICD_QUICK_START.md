# CI/CD Quick Start Guide

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
python -m pytest src/tests/ -v
```

**With coverage:**

```bash
python -m pytest src/tests/ --cov=src --cov-report=term-missing
```

**Expected output:**

```bash
===================== test session starts ======================
collected 170 items

tests/unit/test_config_manager.py::test_load_config PASSED  [ 1%]
tests/unit/test_demo_mode.py::test_start_stop PASSED        [ 2%]
...
================== 170 passed in 5.23s =======================

------------- coverage: platform linux, python 3.14.x --------------
Name                          Stmts   Miss  Cover   Missing
------------------------------------------------------------
config_manager.py               120      8    93%   45-52
demo_mode.py                    156     25    84%   120-145
...
TOTAL                          2341    622    73%
```

**View HTML report:**

```bash
python -m pytest src/tests/ --cov=src --cov-report=html:reports/htmlcov
xdg-open reports/htmlcov/index.html  # Linux
```

---

## Set Up GitHub Secrets

The current CI workflow does not require a `CODECOV_TOKEN`. Coverage is enforced in pytest (`--cov-fail-under=80`) and uploaded as GitHub artifacts.

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

### Enable Branch Protection

- Settings → Branches → Add rule
- ☑ Require pull request reviews
- ☑ Require status checks (`Quality Gate`)
- ☑ Require branches up to date

---

## Common Commands

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
conda activate JuniperCanopy
pip install -r conf/requirements.txt
python -m pytest src/tests/unit/test_demo_mode.py::test_name -vv
```

### CI fails but local passes

```bash
# Test with CI Python version
conda create -n test-py314 python=3.14
conda activate test-py314
pip install -r conf/requirements.txt
python -m pytest src/tests/ -v
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
✅ Made first CI/CD commit  
✅ Viewed CI results

**CI/CD is active!** Every push triggers quality checks, tests, and artifact publication.

---

**Status:** ✅ Ready to use
