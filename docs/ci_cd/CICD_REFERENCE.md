# CI/CD Technical Reference

## Complete technical reference for the CI/CD pipeline

---

## Table of Contents

1. [Pipeline Architecture](#pipeline-architecture)
2. [Workflow Specification](#workflow-specification)
3. [Configuration Files](#configuration-files)
4. [Tool Configurations](#tool-configurations)
5. [Environment Variables](#environment-variables)
6. [Artifact Specifications](#artifact-specifications)
7. [API Reference](#api-reference)
8. [Troubleshooting Reference](#troubleshooting-reference)

---

## Pipeline Architecture

### System Diagram

```mermaid
graph TB
    subgraph "Developer Workstation"
        A[Git Commit]
        B[Pre-commit Hooks]
        A --> B
    end

    subgraph "GitHub"
        C[Git Push]
        D[Workflow Trigger]
        B --> C
        C --> D
    end

    subgraph "GitHub Actions Runners"
        E[Lint Job]
        F[Test Matrix]
        G[Build Job]
        H[Integration Job]
        I[Quality Gate]
        J[Notify]

        D --> E
        D --> F
        E --> G
        F --> G
        F --> H
        G --> I
        H --> I
        I --> J
    end

    subgraph "External Services"
        K[Codecov]
        L[GitHub Checks API]
        F --> K
        J --> L
    end
```

### Job Dependencies

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]

  integration:
    runs-on: ubuntu-latest
    needs: [test]
    if: github.event_name == 'pull_request'

  quality-gate:
    runs-on: ubuntu-latest
    needs: [lint, test, build]
    if: always()

  notify:
    runs-on: ubuntu-latest
    needs: [quality-gate]
    if: always()
```

---

## Workflow Specification

### Trigger Specification

```yaml
on:
  # Push triggers
  push:
    branches:
      - main                # Production branch
      - develop             # Development branch
      - 'feature/**'        # Feature branches
      - 'fix/**'            # Bugfix branches
    paths-ignore:
      - '**.md'             # Skip docs-only changes
      - 'docs/**'
      - 'notes/**'

  # Pull request triggers
  pull_request:
    branches:
      - main
      - develop
    types:
      - opened              # PR created
      - synchronize         # New commits pushed
      - reopened            # PR reopened
      - ready_for_review    # Draft → Ready

  # Manual trigger
  workflow_dispatch:
    inputs:
      python-version:
        description: 'Python version to test'
        required: false
        default: '3.13'
        type: choice
        options:
          - '3.11'
          - '3.12'
          - '3.13'
      skip-slow-tests:
        description: 'Skip slow tests'
        required: false
        default: true
        type: boolean
```

### Job Specification

#### Lint Job

```yaml
lint:
  name: Code Quality Checks
  runs-on: ubuntu-latest
  timeout-minutes: 10

  steps:
    - name: Checkout Code
      uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Full history for better analysis

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.13'
        cache: 'pip'

    - name: Install Linting Tools
      run: |
        python -m pip install --upgrade pip
        pip install black isort flake8 mypy bandit

    - name: Run Black
      run: black --check --diff src/
      continue-on-error: true

    - name: Run isort
      run: isort --check-only --diff src/
      continue-on-error: true

    - name: Run Flake8
      run: |
        flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 src/ --count --max-line-length=120 --statistics --exit-zero
      continue-on-error: true

    - name: Run MyPy
      run: mypy src/ --ignore-missing-imports --no-strict-optional
      continue-on-error: true

    - name: Run Bandit
      run: bandit -r src -c .bandit.yml
      continue-on-error: true
```

#### Test Job

```yaml
test:
  name: Unit Tests + Coverage (Python ${{ matrix.python-version }})
  runs-on: ubuntu-latest
  timeout-minutes: 30

  strategy:
    fail-fast: false
    matrix:
      python-version: ["3.12", "3.13", "3.14"]

  steps:
    - name: Checkout Code
      uses: actions/checkout@v4

    - name: Set up Conda
      uses: conda-incubator/setup-miniconda@v3
      with:
        python-version: ${{ matrix.python-version }}
        channels: conda-forge,pytorch,plotly,defaults
        channel-priority: flexible
        activate-environment: JuniperPython-CI
        environment-file: conf/conda_environment.yaml
        auto-activate-base: false

    - name: Verify Environment
      shell: bash -el {0}
      run: |
        conda info
        conda list
        which python
        python --version

    - name: Install Dependencies
      shell: bash -el {0}
      run: |
        python -m pip install --upgrade pip
        pip install -r conf/requirements.txt

    - name: Run Unit Tests
      shell: bash -el {0}
      run: |
        python -m pytest \
          src/tests \
          --verbose \
          --cov=src \
          --cov-report=xml:reports/coverage.xml \
          --cov-report=term-missing \
          --junit-xml=reports/junit/unit-tests.xml

    - name: Upload Test Results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results-${{ matrix.python-version }}
        path: |
          reports/junit/unit-tests.xml
          reports/coverage.xml
        retention-days: 30

    # Coverage threshold enforcement should be configured in pytest invocation
    # (for example: --cov-fail-under=80)
```

---

## Configuration Files

### .github/workflows/ci.yml

**Last Updated:** 2026-04-04  
**Version:** 0.26.0  
**Status:** Current

## Scope

This reference documents the current CI behavior implemented in:

- `.github/workflows/ci.yml`
- `scripts/check_doc_links.py`
- `conf/requirements_ci.txt`
- `pyproject.toml`

## Workflow Summary

Workflow name: `CI/CD Pipeline`

Trigger events:

- `push` (`main`, `develop`, `feature/**`, `fix/**`)
- `pull_request` (`main`, `develop`)
- `repository_dispatch` (`data-client-updated`, `cascor-client-updated`)
- `workflow_dispatch`

Concurrency:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

**Ignore Patterns:**

```yaml
ignore:
  - src/tests/**           # Test files
  - utils/**               # Utility scripts
  - docs/**                # Documentation
  - "**/__pycache__/**"    # Cache files
```

### pyproject.toml

**Location:** `pyproject.toml`

**Purpose:** Python project and tool configuration

**Sections:**

1. **Project metadata**

   ```toml
   [project]
   name = "juniper-canopy"
   version = "0.4.0"
   requires-python = ">=3.11"
   ```

2. **Black configuration**

   ```toml
   [tool.black]
   line-length = 120
   target-version = ['py311', 'py312', 'py313']
   ```

3. **isort configuration**

### `pre-commit`

- Python matrix: `3.12`, `3.13`, `3.14`
- Installs `pre-commit`
- Runs `pre-commit run --all-files --show-diff-on-failure`
- Caches pre-commit hooks (`~/.cache/pre-commit`)

   ```yaml
   # .bandit.yml
   exclude_dirs:
     - src/tests
     - util/verification
   skips:
     - B311
   confidence: MEDIUM
   severity: MEDIUM
   ```

5. **MyPy configuration**

   ```toml
   [tool.mypy]
   python_version = "3.14"
   ignore_missing_imports = true
   ```

6. **Pytest configuration**

   ```toml
   [tool.pytest.ini_options]
   minversion = "7.0"
   testpaths = ["src/tests"]
   addopts = ["--verbose", "--cov=src"]
   ```

7. **Coverage configuration**

   ```toml
   [tool.coverage.report]
   show_missing = true
   fail_under = 80
   precision = 2
   ```

---

## Tool Configurations

### Black

**Purpose:** Code formatting

**Configuration:**

```toml
[tool.black]
line-length = 120
target-version = ['py311', 'py312', 'py313']
include = '\.pyi?$'
extend-exclude = '''
/(
    \.eggs
    | \.git
    | \.venv
    | logs
    | reports
)/
'''
```

**Usage:**

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --timeout=60 \
  --maxfail=5 \
  --junitxml=reports/junit/junit-unit.xml \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=html:reports/htmlcov \
  --cov-fail-under=80
```

Special behavior:

- Handles Python 3.12 `pytest` cleanup SIGABRT (`exit 134`) by checking JUnit `failures/errors` before deciding failure.

Artifacts:

- `coverage-report-py<version>`
- `unit-test-results-py<version>`

### `integration-tests`

- Python: `3.14`
- Runs only on PRs and pushes to `main`/`develop`
- Marker filter:

```bash
integration and not requires_cascor and not requires_server and not slow
```

Artifact:

- `integration-test-results`

### `build`

- Python: `3.14`
- Uses `python -m build --sdist --wheel`
- Verifies both `.tar.gz` and `.whl`
- Uploads `dist-packages`

### `security`

- Python: `3.14`
- Tools: `gitleaks`, `bandit`, `pip-audit`
- Uploads SARIF and security report artifacts

### `dependency-docs`

```yaml
# .bandit.yml
exclude_dirs:
  - src/tests
  - util/verification
skips:
  - B311
confidence: MEDIUM
severity: MEDIUM
```

Artifact:

```bash
# Security scan
bandit -r src

# With config
bandit -r src -c .bandit.yml

# Specific severity
bandit -r src -ll  # Low severity and up
```

### Lockfile and Dependency Audit

**Purpose:** Keep `requirements.lock` synchronized with `pyproject.toml` extras and audit installed dependencies.

**Usage:**

```bash
# Regenerate lockfile with the same extras used in CI lockfile check
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock

# Mimic CI security job's dependency audit input
pip install dash fastapi uvicorn plotly numpy scipy
pip freeze > reports/security/pip-freeze.txt
pip-audit -r reports/security/pip-freeze.txt --output reports/security/pip-audit.txt
```

**Authoritative workflow files:**

- `.github/workflows/ci.yml`
- `.github/workflows/lockfile-update.yml`
- `.github/workflows/security-scan.yml`

### Pytest

**Purpose:** Testing framework

**Configuration:**

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["src/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--verbose",
    "--color=yes",
    "--cov=src",
    "--cov-report=term-missing"
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow-running tests"
]
```

- Python: `3.14`
- Runs doc link validator with excluded directories/files:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

### `docker-build`

- Builds image from root `Dockerfile`
- Starts container and waits for healthy state
- Verifies:
  - package import
  - `/v1/health` response

### `required-checks`

Aggregates job results and enforces final pass/fail semantics used by branch protection.

## Environment Variables Used in CI

Top-level workflow env:

```yaml
env:
  ENV_NAME: juniper-canopy
  PYTHON_TEST_VERSION: "3.14"
  COVERAGE_FAIL_UNDER: "80"
```

Test gating envs in unit/integration jobs:

```yaml
CASCOR_BACKEND_AVAILABLE: 0
RUN_SERVER_TESTS: 0
ENABLE_SLOW_TESTS: 0
```

## Dependency Reference

Primary CI dependency file:

- `conf/requirements_ci.txt`

Notable required entries:

- `prometheus-client>=0.20.0`
- `sentry-sdk>=2.0.0`

These support observability-import paths used during tests and runtime checks.

## Documentation Link Checker Reference

Script: `scripts/check_doc_links.py`

Core capabilities:

- Validates relative file links and same-file anchors.
- Skips fenced code blocks and inline code spans.
- Supports cross-repo handling modes:
  - `skip` (CI default)
  - `warn`
  - `check`

Exit codes:

- `0`: all valid
- `1`: broken links or invalid arguments

## Common Failure Classes

### Stale lockfile

Symptom:

- `lockfile-check` fails diff

Fix:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### Broken docs links

Symptom:

- `docs` job reports missing files/anchors

Fix:

- run checker locally with the CI command and repair relative paths or heading anchors

### Optional testing modules skipped

Symptom:

- Service/e2e tests skipped via `importorskip`

Fix (local full-run only):

```bash
pip install "juniper-cascor-client[testing]"
pip install "juniper-data-client[testing]"
```

## Related Docs

**Last Updated:** 2026-04-05  
**Version:** 0.25.1  
**Maintained By:** Development Team  
**Status:** ✅ Current
