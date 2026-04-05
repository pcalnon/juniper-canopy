# CI/CD Technical Reference

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

- [Workflow Inventory](#workflow-inventory)
- [Main CI Workflow (`ci.yml`)](#main-ci-workflow-ciyml)
- [Auxiliary Workflows](#auxiliary-workflows)
- [Tooling and Configuration Sources](#tooling-and-configuration-sources)
- [Artifacts Produced by CI](#artifacts-produced-by-ci)
- [Command Equivalents for Local Reproduction](#command-equivalents-for-local-reproduction)

## Workflow Inventory

| Workflow File | Trigger | Primary Purpose |
| --- | --- | --- |
| `.github/workflows/ci.yml` | `push`, `pull_request`, `repository_dispatch`, `workflow_dispatch` | Full quality pipeline and merge gate |
| `.github/workflows/security-scan.yml` | weekly cron + manual | Scheduled security posture scan |
| `.github/workflows/lockfile-update.yml` | Dependabot push branches | Auto-refresh `requirements.lock` |
| `.github/workflows/publish.yml` | release published | Build + TestPyPI + PyPI publish |

## Main CI Workflow (`ci.yml`)

### Trigger and concurrency

    - name: Run Bandit
      run: bandit -r src/ -c pyproject.toml
      continue-on-error: true
```

#### Test Job

```yaml
test:
  name: Test Suite (Python ${{ matrix.python-version }})
  runs-on: ubuntu-latest
  timeout-minutes: 30

  strategy:
    fail-fast: false
    matrix:
      python-version: ["3.11", "3.12", "3.13"]

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

    - name: Run Tests
      shell: bash -el {0}
      run: |
        cd src
        pytest tests/ \
          --verbose \
          --cov=. \
          --cov-report=xml:../coverage.xml \
          --cov-report=term-missing \
          --cov-report=html:../reports/coverage \
          --junit-xml=../reports/junit/results.xml \
          --html=../reports/test_report.html \
          --self-contained-html

    - name: Upload Coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        token: ${{ secrets.CODECOV_TOKEN }}
        fail_ci_if_error: false
      continue-on-error: true

    - name: Upload Test Results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results-${{ matrix.python-version }}
        path: |
          reports/
          coverage.xml
        retention-days: 30

    - name: Check Coverage Threshold
      shell: bash -el {0}
      run: |
        cd src
        COVERAGE=$(pytest tests/ --cov=. --cov-report=term-missing | grep "TOTAL" | awk '{print $NF}' | sed 's/%//')
        echo "Current coverage: ${COVERAGE}%"

        if (( $(echo "$COVERAGE < 80" | bc -l) )); then
          echo "::warning::Coverage below 80%: ${COVERAGE}%"
        fi

        if (( $(echo "$COVERAGE < 60" | bc -l) )); then
          echo "::error::Coverage critically low: ${COVERAGE}%"
          exit 1
        fi
      continue-on-error: true
```

#### Documentation Links Job

**Purpose:** Validate internal documentation links and heading anchors in markdown files.

**Workflow step (from `.github/workflows/ci.yml`):**

```yaml
docs:
  name: Documentation Links
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@...
    - uses: actions/setup-python@...
      with:
        python-version: "3.14"
    - name: Validate Documentation Links
      run: |
        python scripts/check_doc_links.py \
          --exclude templates --exclude history \
          --exclude pull_requests --exclude releases \
          --exclude analysis --exclude fixes --exclude development \
          --exclude CHANGELOG.md \
          --cross-repo skip
```

**Validated code paths (`scripts/check_doc_links.py`):**

1. Relative documentation links resolve to existing files.
2. Same-file anchors (for example, `#heading`) map to real markdown headings.
3. Links inside fenced code blocks and inline code spans are ignored by design.
4. External URLs (`http`, `https`, `mailto`, `ftp`) are skipped.
5. Security checks reject absolute paths, null-byte targets, and excessive traversal depth.

**Cross-repo policy modes:**

- `skip`: Ignore ecosystem sibling links (CI default, deterministic in isolated runners).
- `warn`: Print warnings for sibling links without failing.
- `check`: Validate sibling links against a discovered local Juniper ecosystem root.

**Local reproduction commands:**

```bash
# Match CI behavior
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip

# Strict local validation (requires sibling repos checked out)
python scripts/check_doc_links.py --cross-repo check
```

---

### Global environment

```yaml
env:
  ENV_NAME: juniper-canopy
  PYTHON_TEST_VERSION: "3.14"
  COVERAGE_FAIL_UNDER: "80"
```

### Jobs and dependencies

| Job | Needs | Python | Notes |
| --- | --- | --- | --- |
| `pre-commit` | — | matrix `3.12/3.13/3.14` | Runs `pre-commit --all-files` |
| `unit-tests` | `pre-commit` | matrix `3.12/3.13/3.14` | Runs unit + regression markers with coverage gate |
| `integration-tests` | `unit-tests` | `3.14` | Runs fast integration subset |
| `build` | `unit-tests` | `3.14` | Builds sdist and wheel |
| `security` | `pre-commit` | `3.14` | Gitleaks + Bandit + pip-audit |
| `dependency-docs` | `build` | `3.14` | Generates dependency docs via script |
| `lockfile-check` | — | `3.14` | Recompiles lockfile and diffs body |
| `docs` | — | `3.14` | Runs doc-link validation script |
| `docker-build` | `build` | docker engine | Builds image + health smoke test |
| `required-checks` | all core jobs | n/a | Aggregated merge gate |
| `notify` | `required-checks` | n/a | Run summary |

### Test marker expressions in CI

Unit/regression gate:

```bash
-m "not requires_cascor and not requires_server and not slow"
```

Integration gate:

```bash
-m "integration and not requires_cascor and not requires_server and not slow"
```

### Coverage gate

Unit tests enforce:

```bash
--cov-fail-under=${COVERAGE_FAIL_UNDER}
```

With current `COVERAGE_FAIL_UNDER=80`.

### Lockfile freshness behavior

CI compiles with:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
```

Then strips first two lines from both lockfiles before diffing to avoid path-only header differences.

### Documentation links behavior

CI validates links with:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

This catches broken internal file and heading links without requiring sibling repos.

## Auxiliary Workflows

### `security-scan.yml`

- Scheduled: Mondays at `06:00 UTC`
- Installs `bandit[sarif]` and `pip-audit`
- Runs:
  - `bandit -r src -c .bandit.yml -f sarif ... --exit-zero`
  - `bandit -r src -c .bandit.yml --confidence-level medium --severity-level medium`
  - `pip-audit --strict --desc on`
- Uploads `reports/security/` artifacts

### `lockfile-update.yml`

- Trigger: push to `dependabot/pip/**`
- Guard: `if: github.actor == 'dependabot[bot]'`
- Uses `CROSS_REPO_DISPATCH_TOKEN` for checkout/push
- Compiles lockfile with:
  - `--extra juniper-data`
  - `--extra juniper-cascor`
- Commits only when diff exists

### `publish.yml`

- Trigger: GitHub release published
- `id-token: write` for trusted publishing
- Stages:
  1. Build + `twine check`
  2. Publish to TestPyPI + install verification
  3. Publish to PyPI

## Tooling and Configuration Sources

| Concern | Source of Truth |
| --- | --- |
| Pytest markers and defaults | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Coverage thresholds | `pyproject.toml` and `ci.yml` job args |
| CI dependencies | `conf/requirements_ci.txt` |
| Security scan excludes | `.bandit.yml` + workflow commands |
| Doc-link validation rules | `scripts/check_doc_links.py` |

## Artifacts Produced by CI

| Job | Artifact | Typical Contents |
| --- | --- | --- |
| `unit-tests` | `coverage-report-py*` | XML + HTML coverage outputs |
| `unit-tests` | `unit-test-results-py*` | JUnit XML test outputs |
| `integration-tests` | `integration-test-results` | Integration JUnit XML |
| `build` | `dist-packages` | Wheel and sdist |
| `security` | `security-reports` | Bandit + pip-audit reports |
| `dependency-docs` | `dependency-docs` | Generated requirements/conda docs |

| Error | Cause                    | Solution                         |
| ----- | ------------------------ | -------------------------------- |
| E001  | Workflow syntax error    | Validate YAML syntax             |
| E002  | Missing required field   | Add required field to workflow   |
| E003  | Invalid expression       | Fix workflow expression syntax   |
| E101  | Job timeout              | Increase timeout or optimize job |
| E102  | Job cancelled            | Check concurrency settings       |
| E201  | Step failed              | Check step logs for details      |
| E202  | Command not found        | Install required tool            |
| E203  | Permission denied        | Check file permissions           |
| E301  | Artifact upload failed   | Check size and path              |
| E302  | Artifact download failed | Verify artifact exists           |

### Documentation Link Validation Failures

| Symptom | Likely Cause | Resolution |
| ----- | ----- | ----- |
| `broken anchor #... (heading not found)` | Anchor does not match generated heading slug | Rename anchor to match markdown heading text normalization |
| `absolute path in documentation link` | Link target starts with `/` | Replace absolute target with a repository-relative path |
| `excessive directory traversal in link` | Link contains too many `..` segments | Rewrite link to a shorter, repo-bounded relative path |
| `null byte in link target` | Invalid link target string | Remove malformed target and re-add a valid path |
| `Cross-repo links: skip` in CI output | CI is intentionally skipping sibling-repo checks | Run locally with `--cross-repo check` only when sibling repos are available |

### Exit Codes

| Code | Meaning                 |
| ---- | ----------------------- |
| 0    | Success                 |
| 1    | General error           |
| 2    | Misuse of shell command |
| 126  | Command cannot execute  |
| 127  | Command not found       |
| 128  | Invalid exit argument   |
| 130  | Terminated by Ctrl+C    |
| 137  | Killed (out of memory)  |
| 139  | Segmentation fault      |

### Log Analysis

**Search patterns:**

```bash
# Pre-commit
pre-commit run --all-files

# Unit/regression gate
cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose \
  --cov=. \
  --cov-report=term-missing \
  --cov-fail-under=80

# Integration gate
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose

# Lockfile gate
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock

| Stage            | Duration | CPU     | Memory |
| ---------------- | -------- | ------- | ------ |
| Lint             | 2 min    | 1 core  | 512 MB |
| Test (each)      | 8 min    | 2 cores | 2 GB   |
| Build            | 2 min    | 1 core  | 512 MB |
| Integration      | 5 min    | 2 cores | 1 GB   |
| Quality Gate     | 30 sec   | 1 core  | 256 MB |
| Total (parallel) | ~15 min  | -       | -      |

### Optimization Targets

| Metric            | Current | Target | Stretch |
| ----------------- | ------- | ------ | ------- |
| Total build time  | 15 min  | 10 min | 7 min   |
| Test suite        | 8 min   | 5 min  | 3 min   |
| Lint              | 2 min   | 1 min  | 30 sec  |
| Coverage overhead | 20%     | 10%    | 5%      |

---

## Version History

### Version 1.0.0 (2025-11-05)

**Initial release:**

- Complete CI/CD pipeline
- Multi-version Python testing
- Coverage reporting
- Pre-commit hooks
- Quality gates
- Comprehensive documentation

---

## References

### Official Documentation

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Pytest Docs](https://docs.pytest.org/)
- [Coverage.py Docs](https://coverage.readthedocs.io/)
- [Pre-commit Docs](https://pre-commit.com/)
- [Codecov Docs](https://docs.codecov.com/)

### Project Documentation

- [CICD_QUICK_START.md](CICD_QUICK_START.md)
- [CICD_ENVIRONMENT_SETUP.md](CICD_ENVIRONMENT_SETUP.md)
- [CICD_MANUAL.md](CICD_MANUAL.md)
- [AGENTS.md](../../AGENTS.md)
- [README.md](../../README.md)

---

**Last Updated:** 2026-04-05  
**Version:** 0.25.1  
**Maintained By:** Development Team  
**Status:** ✅ Current
