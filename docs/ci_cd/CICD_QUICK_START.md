# CI/CD Quick Start Guide

**Last Updated:** 2026-04-04  
**Time to Complete:** ~5 minutes  
**Version:** 0.25.2

---

## Prerequisites

- ✅ Conda environment activated (`JuniperPython`)
- ✅ Dependencies installed (`pip install -r conf/requirements.txt`)
- ✅ Git repository initialized
- ✅ Python 3.12+ installed

**Verify:**

```bash
python --version      # Should be 3.12+
pytest --version      # Should be 7.0+
conda env list | grep JuniperPython  # Should show active
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
cd src
pytest tests/ -v
```

**With coverage:**

```bash
cd src
pytest tests/ --cov=. --cov-report=term-missing
```

**Expected output:**

```bash
===================== test session starts ======================
collected 170 items

tests/unit/test_config_manager.py::test_load_config PASSED  [ 1%]
tests/unit/test_demo_mode.py::test_start_stop PASSED        [ 2%]
...
================== 170 passed in 5.23s =======================

------------- coverage: platform linux, python 3.13.x --------------
Name                          Stmts   Miss  Cover   Missing
------------------------------------------------------------
config_manager.py               120      8    93%   45-52
demo_mode.py                    156     25    84%   120-145
...
TOTAL                          2341    622    73%
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
├── ✓ Pre-commit (Python 3.12/3.13/3.14)  ~2-3 min
├── ✓ Unit Tests + Coverage (3.12/3.13/3.14) ~8 min
├── ✓ Integration Tests                   ~5 min
├── ✓ Security Scans                      ~3-5 min
├── ✓ Lockfile Freshness                  ~1 min
├── ✓ Documentation Links                 ~1 min
├── ✓ Docker Build & Smoke Test           ~3-6 min
├── ✓ Build Distribution                  ~2 min
├── ✓ Quality Gate                        ~30 sec
└── ✓ Notify                           ~10 sec

Total: ~10 minutes
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
- ☑ Require status checks (`Quality Gate` and other required jobs)
- ☑ Require branches up to date

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
conda activate JuniperPython
pip install -r conf/requirements.txt
pytest tests/unit/test_demo_mode.py::test_name -vv
```

### CI fails but local passes

```bash
# Test with CI Python version
conda create -n test-py312 python=3.12
conda activate test-py312
pip install -r conf/requirements.txt
cd src && pytest tests/ -v
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
