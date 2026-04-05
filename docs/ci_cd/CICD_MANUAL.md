# CI/CD Manual

**Last Updated:** 2026-04-05  
**Version:** 0.26.0  
**Status:** Current

## Table of Contents

- [Overview](#overview)
- [Pipeline Intent and Architecture](#pipeline-intent-and-architecture)
- [Developer Workflow](#developer-workflow)
- [Maintainer Runbooks](#maintainer-runbooks)
- [Quality Gates and Merge Criteria](#quality-gates-and-merge-criteria)
- [Troubleshooting by Failing Job](#troubleshooting-by-failing-job)

## Overview

This manual describes how the current GitHub Actions pipeline works and how to operate it safely.
It is source-verified against:

- `.github/workflows/ci.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/lockfile-update.yml`
- `.github/workflows/publish.yml`
- `pyproject.toml`
- `scripts/check_doc_links.py`

## Pipeline Intent and Architecture

The pipeline enforces three outcomes:

- Code quality and test safety (`pre-commit`, `unit-tests`, `integration-tests`)
- Supply-chain and security hygiene (`security`, lockfile, scheduled scan)
- Operational correctness of artifacts and docs (`build`, `docker-build`, `docs`, `dependency-docs`)

Primary workflow (`ci.yml`) flow:

1. `pre-commit` runs on Python `3.12/3.13/3.14`
2. `unit-tests` runs matrix tests with coverage gate (`--cov-fail-under=80`)
3. `build` runs once on Python `3.14`
4. Parallel validation jobs run:
   - `integration-tests`
   - `security`
   - `dependency-docs`
   - `lockfile-check`
   - `docs`
   - `docker-build`
5. `required-checks` aggregates results and blocks on failures
6. `notify` emits final summary

## Developer Workflow

### 1. Before pushing a branch

```bash
pre-commit run --all-files

cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose \
  --cov=. \
  --cov-report=term-missing
```

For integration-sensitive changes:

```bash
cd src
python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose
```

### 2. If dependencies changed

Regenerate lockfile exactly as CI expects:

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

### 3. If docs changed

Validate links with CI-equivalent arguments:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

## Maintainer Runbooks

### Runbook: Dependabot lockfile automation

When Dependabot pushes to `dependabot/pip/**`, `lockfile-update.yml`:

1. Regenerates `requirements.lock` via `uv pip compile`
2. Commits `[dependabot skip] Update requirements.lock` if changed
3. Pushes with `CROSS_REPO_DISPATCH_TOKEN` so downstream CI is triggered

Operational constraints:

- Keep `CROSS_REPO_DISPATCH_TOKEN` valid
- Keep compile extras aligned with `ci.yml` (`juniper-data`, `juniper-cascor`, `observability`)
- Keep `requirements.lock` committed in PRs that modify dependency constraints

### Runbook: Scheduled security scan

`security-scan.yml` runs weekly and manually:

1. Installs `bandit[sarif]`, `pip-audit`, and project package (`pip install -e .`)
2. Runs Bandit with SARIF output and text output
3. Runs `pip-audit --strict --desc on`
4. Uploads `reports/security/` artifacts

Use this runbook after dependency updates to confirm no new vulnerabilities are introduced.

### Runbook: Release publishing

`publish.yml` is release-triggered (`release: published`) and uses OIDC:

1. Build and `twine check`
2. Publish to TestPyPI (`environment: testpypi`)
3. Verify installation from TestPyPI
4. Publish to PyPI (`environment: pypi`)

Do not bypass TestPyPI stage; production publish is intentionally downstream.

## Quality Gates and Merge Criteria

PRs are merge-safe when `Quality Gate` succeeds.

`required-checks` enforces:

- Must succeed:
  - `pre-commit`
  - `unit-tests`
  - `lockfile-check`
- Must not fail:
  - `integration-tests` (allowed skipped outside configured refs)
  - `security`
  - `docs`
  - `dependency-docs` (skipped acceptable, failure not)
  - `docker-build` (skipped acceptable, failure not)

#### Flaky Test Management

**Identify flaky tests:**

```bash
# Run test multiple times
for i in {1..10}; do
    pytest tests/unit/test_suspected_flaky.py -v || echo "FAIL $i"
done
```

**Common causes:**

1. **Timing/race conditions:**

   ```python
   # Bad
   time.sleep(0.1)
   assert condition

   # Good
   for i in range(50):  # 5 seconds total
       if condition:
           break
       time.sleep(0.1)
   else:
       assert False, "Timeout waiting for condition"
   ```

2. **Shared state:**

   ```python
   # Bad: Tests depend on execution order

   # Good: Each test independent
   def test_feature(reset_singleton):
       # Fixture resets state
   ```

3. **External dependencies:**

   ```python
   # Bad: Depends on network
   response = requests.get("https://api.example.com")

   # Good: Mock external calls
   @patch('requests.get')
   def test_api_call(mock_get):
       mock_get.return_value.json.return_value = {...}
   ```

### Managing Codecov

#### Setup and Configuration

**File:** `.codecov.yml`

```yaml
coverage:
  precision: 2
  round: down
  range: 70..100

  status:
    project:
      default:
        target: 80%
        threshold: 5%
    patch:
      default:
        target: 60%
        threshold: 10%
```

#### Understanding Codecov Reports

**PR Comment:**

```markdown
## Codecov Report

Coverage: 73.45% (+0.23%)
Files Changed: 3
Lines Changed: +45 / -12

| File                 | Coverage | Δ     |
| -------------------- | -------- | ----- |
| config_manager.py    | 93.2%    | +2.1% |
| demo_mode.py         | 84.5%    | -1.2% |
| websocket_manager.py | 78.3%    | +0.5% |
```

**Interpreting:**

- **Overall coverage:** 73.45% (up from 73.22%)
- **Δ** (delta): Change from base branch
- **Green:** Coverage increased
- **Red:** Coverage decreased

#### Troubleshooting Codecov

**Coverage not uploading:**

```yaml
# Check GitHub Actions logs
- name: Upload Coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    file: ./coverage.xml
    token: ${{ secrets.CODECOV_TOKEN }}  # Verify secret set
    fail_ci_if_error: false  # Change to true to debug
```

**Coverage report missing files:**

```yaml
# Check .codecov.yml ignore section
ignore:
  - src/tests/**  # Are you ignoring too much?
```

---

## Workflow Deep Dive

### Lint Stage

**Purpose:** Enforce code quality standards

**Tools:**

1. **Black** - Code formatting
2. **isort** - Import sorting
3. **Flake8** - Linting
4. **MyPy** - Type checking (optional)

**Duration:** ~2 minutes

**Failure conditions:**

- Syntax errors
- Undefined names
- Critical code smells

**Note:** Style warnings don't fail build

### Test Stage

**Purpose:** Run test suite across Python versions

**Matrix:**

```yaml
python-version: ["3.11", "3.12", "3.13"]
```

**For each version:**

1. Set up Conda environment
2. Install dependencies
3. Run pytest with coverage
4. Generate reports (XML, HTML, JUnit)
5. Upload to Codecov
6. Upload artifacts
7. Check coverage threshold

**Duration:** ~8 minutes per version

**Failure conditions:**

- Any test fails
- Coverage <60%
- Collection errors

### Build Stage

**Purpose:** Verify project can be packaged

**Steps:**

1. Verify project structure
2. Check Python syntax
3. Generate build metadata

**Duration:** ~2 minutes

**Failure conditions:**

- Syntax errors
- Missing critical files

### Integration Stage

**Purpose:** Test component interactions

**When:** Pull requests only

**Steps:**

1. Run integration tests (`tests/integration/`)
2. Skip external dependencies (`-m "not requires_cascor"`)

**Duration:** ~5 minutes

**Failure conditions:**

- Integration test failures

### Quality Gate Stage

**Purpose:** Aggregate results and enforce standards

**Checks:**

```python
if test_result == "failure":
    fail("Tests failed")
elif build_result == "failure":
    fail("Build failed")
elif lint_result == "failure":
    warn("Linting failed")
else:
    pass("Quality gate passed")
```

**Duration:** ~30 seconds

### Notify Stage

**Purpose:** Report final status

**Information logged:**

- Workflow name
- Branch
- Commit SHA
- Actor (who triggered)
- Final status

**Duration:** ~10 seconds

---

## Quality Gates and Metrics

### Coverage Metrics

**Overall coverage:**

```bash
Current:  73%
Target:   80%
Minimum:  60%
```

**By module:**

| Module            | Current | Target | Status     |
| ----------------- | ------- | ------ | ---------- |
| config_manager    | 93%     | 100%   | ⚠️ Close   |
| demo_mode         | 84%     | 100%   | ⚠️ Close   |
| websocket_manager | 78%     | 100%   | ❌ Gap     |
| dashboard_manager | 84%     | 60%    | ✅ Exceeds |
| metrics_panel     | 94%     | 60%    | ✅ Exceeds |

### Test Metrics

**Test counts:**

```bash
Total:        170 tests
Unit:         120 tests (71%)
Integration:   40 tests (23%)
Performance:   10 tests (6%)
```

**Pass rate:**

```bash
Required:     100%
Current:      100%
Status:       ✅ Pass
```

### Performance Metrics

**Build times:**

```bash
Lint:         2 min
Test (3.11):  8 min
Test (3.12):  8 min
Test (3.13):  8 min
Build:        2 min
Integration:  5 min
Total:        ~15 min (with parallelization)
```

**Targets:**

- Total build: <20 min
- Individual job: <10 min
- Critical path: <15 min

---

## Debugging Failed Builds

### Systematic Debugging Process

**1. Identify failure type:**

```bash
✓ Lint
✗ Test Suite (Python 3.13)
✓ Build
✓ Integration
✗ Quality Gate
```

**2. Examine failed job:**

- Click on failed job
- Expand failed step
- Read error message

**3. Reproduce locally:**

```bash
# Match CI environment
conda create -n debug-ci python=3.13
conda activate debug-ci
pip install -r conf/requirements.txt

# Run failing test
cd src
pytest tests/unit/test_failing.py -vv
```

**4. Debug with more verbosity:**

```bash
# Maximum verbosity
pytest tests/ -vv -s --tb=long

# Drop into debugger on failure
pytest tests/ --pdb

# Show local variables
pytest tests/ --showlocals
```

**5. Fix and verify:**

```bash
# Fix code
vim src/module.py

# Verify fix
pytest tests/unit/test_module.py -v

# Run full suite
pytest tests/ -v
```

**6. Push fix:**

```bash
git add src/module.py
git commit -m "fix: Resolve test failure in module"
git push
```

### Common Failure Patterns

#### Pattern 1: Import Error

**Symptom:**

```bash
ERROR: ModuleNotFoundError: No module named 'uvicorn'
```

**Causes:**

1. Missing from `requirements.txt`
2. Conda environment not activated
3. Typo in import statement

**Fix:**

```bash
# Add to requirements.txt
echo "uvicorn>=0.20.0" >> conf/requirements.txt

# Verify locally
pip install -r conf/requirements.txt
pytest tests/ -v
```

#### Pattern 2: Fixture Not Found

**Symptom:**

```bash
ERROR: fixture 'mock_config_file' not found
```

**Causes:**

1. `conftest.py` not in correct location
2. Fixture name typo
3. Pytest not discovering fixtures

**Fix:**

```bash
# Ensure conftest.py at tests root
ls src/tests/conftest.py

# Check fixture definition
grep "def mock_config_file" src/tests/conftest.py
```

#### Pattern 3: Assertion Failure

**Symptom:**

```bash
FAILED tests/unit/test_demo_mode.py::test_metrics
AssertionError: assert {'epoch': 1} == {'epoch': 0}
```

**Causes:**

1. Logic bug
2. Test assumption wrong
3. Race condition
4. State not reset

**Fix:**

```python
# Debug test
def test_metrics():
    demo = DemoMode()
    demo.start()

    # Add debug output
    state = demo.get_current_state()
    print(f"State: {state}")  # Use -s flag to see

    assert state['epoch'] == 0
```

#### Pattern 4: Coverage Too Low

**Symptom:**

```bash
ERROR: Coverage is critically low: 55% (minimum: 60%)
```

**Causes:**

1. New code without tests
2. Tests deleted
3. Dead code added

**Fix:**

```bash
# Generate coverage report
cd src
pytest tests/ --cov=. --cov-report=html

# View report
open ../reports/coverage/index.html

# Add tests for uncovered code
vim tests/unit/test_new_feature.py
```

#### Pattern 5: Documentation Link Validation Failure

**Symptom:**

```bash
FOUND 1 broken link(s) in 1 file(s):
docs/xyz.md:42: broken anchor #missing-heading (heading not found)
```

**Causes:**

1. Heading anchor does not match markdown heading slug generation
2. Link target points to a moved/deleted file
3. Link uses absolute paths or unsafe traversal patterns
4. CI runner uses `--cross-repo skip`, masking sibling-repo checks you expected

**Fix:**

```bash
# Run exactly what CI runs
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip

# Optional strict mode for local ecosystem checkouts
python scripts/check_doc_links.py --cross-repo check
```

---

## Performance Optimization

### Current Performance

**Baseline:**

```bash
Lint:         2 min
Test Matrix:  24 min (8 min × 3 versions)
Build:        2 min
Integration:  5 min
Total:        33 min sequential
              15 min parallel (current)
```

### Optimization Strategies

#### 1. Dependency Caching

**Before:** Install dependencies every run (~2 min)

**After:** Cache dependencies (~30 sec)

```yaml
- name: Cache pip packages
  uses: actions/cache@668228422ae6a00e4ad889ee87cd7109ec5666a7  # v5.0.4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

**Savings:** ~1.5 min per job

#### 2. Pytest Cache

**Before:** Full test discovery every run

**After:** Cache test results

```yaml
- name: Cache pytest
  uses: actions/cache@668228422ae6a00e4ad889ee87cd7109ec5666a7  # v5.0.4
  with:
    path: src/.pytest_cache
    key: ${{ runner.os }}-pytest-${{ hashFiles('**/tests/**') }}
```

**Savings:** ~10-20 seconds

#### 3. Parallel Test Execution

**Before:** Tests run sequentially

**After:** Tests run in parallel

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest tests/ -n auto  # Auto-detect CPU count
pytest tests/ -n 4     # Use 4 workers
```

**Savings:** 30-50% reduction in test time

#### 4. Skip Slow Tests

**Mark slow tests:**

```python
@pytest.mark.slow
def test_long_running_operation():
    # Takes 30+ seconds
    pass
```

**Skip in CI:**

```yaml
- name: Run Tests (skip slow)
  run: pytest tests/ -m "not slow"
```

**Savings:** Variable, depends on slow tests

#### 5. Optimize Matrix

**Before:** Test all versions

```yaml
matrix:
  python-version: ["3.11", "3.12", "3.13"]
```

**After:** Primary version + periodic full matrix

```yaml
matrix:
  python-version: ["3.13"]  # Fast feedback

# Full matrix on:
# - Pull requests to main
# - Nightly builds
# - Release tags
```

**Savings:** ~16 min (2 fewer versions)

### Recommended Optimizations

#### Phase 1: Quick wins

1. Add pip caching
2. Add pytest caching
3. Skip slow tests on non-main branches

**Expected improvement:** 15 min → 10 min

#### Phase 2: Medium effort

1. Use pytest-xdist for parallel tests
2. Optimize test fixtures
3. Conditional matrix (single version for PRs)

**Expected improvement:** 10 min → 7 min

#### Phase 3: Advanced

1. Split test suite into shards
2. Use self-hosted runners
3. Implement test impact analysis

**Expected improvement:** 7 min → 5 min

---

## Security Considerations

### Secrets Management

**Never commit:**

- API keys
- Passwords
- Private keys
- Tokens
- Certificates

**Always use GitHub Secrets:**

```yaml
- name: Use Secret
  env:
    TOKEN: ${{ secrets.API_TOKEN }}
  run: |
    # Secret available as $TOKEN
    # Never echo the value!
```

### Security Scanning

**Bandit security scanner:**

```yaml
- name: Security Scan
  run: bandit -r src/ -c pyproject.toml
```

**Common issues caught:**

- Hardcoded passwords
- SQL injection
- Use of `eval()`/`exec()`
- Insecure random

### Dependency Security

**Dependabot alerts:**

1. Enable Dependabot in repository settings
2. Review alerts weekly
3. Update vulnerable dependencies promptly

**Example:**

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Code Scanning

**GitHub Advanced Security:**

1. Enable code scanning
2. Run CodeQL analysis
3. Review and fix findings

```yaml
# .github/workflows/codeql.yml
- name: Initialize CodeQL
  uses: github/codeql-action/init@v2
  with:
    languages: python
```

---

## Emergency Procedures

### Build System Down

**Symptoms:**

- All workflows failing
- GitHub Actions unavailable
- Runners not available

**Actions:**

1. Check [GitHub Status](https://www.githubstatus.com)
2. If outage, wait for resolution
3. Communicate to team
4. Delay merges until restored

**Workaround:**

```bash
# Run tests locally before merge
pytest tests/ --cov=. -v

# Get manual approval from maintainer
# Merge with --no-verify if urgent
```

### Critical Bug in Production

**Scenario:** Need to deploy fix immediately

**Procedure:**

```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-fix

# 2. Make minimal fix
vim src/broken_module.py

# 3. Test locally
pytest tests/ -v

# 4. Commit
git commit -am "hotfix: Fix critical bug"

# 5. Push
git push origin hotfix/critical-fix

# 6. Create PR
# Title: "[HOTFIX] Fix critical bug"

# 7. Request immediate review

# 8. If CI taking too long and fix is verified:
# - Get approval from 2+ maintainers
# - Merge despite CI running
# - Monitor CI completion
# - Revert if CI fails
```

### Coverage Threshold Blocking Valid Work

**Scenario:** Coverage drop due to external factors

**Temporary bypass:**

```yaml
# .github/workflows/ci.yml
- name: Check Coverage Threshold
  run: |
    # Temporarily disabled due to refactoring
    echo "Coverage check disabled - Issue #789"
  continue-on-error: true
```

**Process:**

1. Create issue documenting reason
2. Set deadline for re-enabling
3. Announce to team
4. Track progress on issue
5. Re-enable threshold
6. Close issue

### Flaky Test Epidemic

**Scenario:** Multiple tests failing intermittently

**Immediate action:**

```bash
# Disable flaky tests temporarily
# File: tests/unit/test_flaky.py

@pytest.mark.skip(reason="Flaky - Issue #456")
def test_problematic():
    pass
```

**Create issues:**

```markdown
# Issue: Fix flaky test_websocket_connection

## Symptoms
- Fails ~30% of time
- ConnectionRefusedError
- Only on CI, not local

## Investigation needed
- [ ] Check timing assumptions
- [ ] Review WebSocket lifecycle
- [ ] Add retries
- [ ] Improve test isolation

## Deadline
Fix by: 2025-11-12

### Track and fix systematically
```

- Unit-test matrix uses `--cov-fail-under=80` from workflow env and pytest command line.

## Troubleshooting by Failing Job

### `unit-tests` failing on one Python version only

- Reproduce with that interpreter locally.
- Confirm dependency compatibility with `conf/requirements_ci.txt`.
- Re-run marker-filtered command from this manual.

### `lockfile-check` fails with diff

- Recompile `requirements.lock` using all three extras.
- Ensure no manual edits were made to lockfile body.

### `docs` fails

- Run `scripts/check_doc_links.py` with workflow excludes and `--cross-repo skip`.
- Fix broken relative paths or heading anchors.

### `dependency-docs` fails

- Re-run `scripts/generate_dep_docs.sh` locally.
- Validate `conf/conda_environment_ci.yaml` parses and contains dependencies.

### `docker-build` fails

- Build local image from root `Dockerfile`.
- Start container and verify `/v1/health` response.
- Check image startup logs for import/config errors.

### `security` fails

- For Bandit: review `reports/security/bandit.txt` and prioritize medium/high findings.
- For pip-audit: update vulnerable dependencies and regenerate lockfile.

## References

- [CI/CD Quick Start](CICD_QUICK_START.md)
- [CI/CD Environment Setup](CICD_ENVIRONMENT_SETUP.md)
- [CI/CD Reference](CICD_REFERENCE.md)
- [Testing Manual](../testing/TESTING_MANUAL.md)
