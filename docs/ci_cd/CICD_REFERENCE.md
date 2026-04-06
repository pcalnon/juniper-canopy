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

- Triggers on pushes to `main`, `develop`, `feature/**`, `fix/**`
- Triggers on PRs targeting `main` and `develop`
- Supports `repository_dispatch` for dependency-change events
- Uses concurrency group `ci-${{ github.ref }}` with `cancel-in-progress: true`

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

## Command Equivalents for Local Reproduction

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
```

### Codecov API

#### Upload Coverage

```bash
curl -X POST \
  --data-binary @coverage.xml \
  -H "Authorization: token $CODECOV_TOKEN" \
  https://codecov.io/upload/v4
```

#### Get Coverage Report

```bash
curl https://codecov.io/api/v2/repos/OWNER/REPO/coverage
```

---

## Troubleshooting Reference

### Common Error Codes

| Error | Cause                    | Solution                            |
|-------|--------------------------|-------------------------------------|
| E001  | Workflow syntax error    | Validate YAML syntax                |
| E002  | Missing required field   | Add required field to workflow      |
| E003  | Invalid expression       | Fix workflow expression syntax      |
| E101  | Job timeout              | Increase timeout or optimize job    |
| E102  | Job cancelled            | Check concurrency settings          |
| E201  | Step failed              | Check step logs for details         |
| E202  | Command not found        | Install required tool               |
| E203  | Permission denied        | Check file permissions              |
| E301  | Artifact upload failed   | Check size and path                 |
| E302  | Artifact download failed | Verify artifact exists              |
| D401  | Broken markdown link     | Update link target path             |
| D402  | Broken heading anchor    | Update anchor or heading            |
| D403  | Unsafe link path         | Remove absolute/null/deep traversal |

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
# Errors
grep -i "error" workflow.log

# Warnings
grep -i "warning" workflow.log

# Failed tests
grep "FAILED" workflow.log

# Coverage issues
grep "coverage" workflow.log | grep -i "low\|fail"
```

### Documentation Link Validation Failures

**Symptom:**

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o /tmp/requirements.lock.check
mv /tmp/requirements.lock.check requirements.lock
```

**Local reproduction (CI-equivalent):**

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

**Common causes:**

- Moved/renamed markdown files without updating references
- Heading text changed but same-file anchor remained unchanged
- Absolute paths in markdown links
- Directory traversal links that resolve outside repository boundaries

**Fix approach:**

1. Update links to repository-relative paths.
2. Regenerate heading anchors from the current markdown heading text.
3. Re-run the command above before pushing.

---

## Performance Metrics

### Baseline Performance

| Stage            | Duration | CPU     | Memory |
| ---------------- | -------- | ------- | ------ |
| Lint             | 2 min    | 1 core  | 512 MB |
| Test (each)      | 8 min    | 2 cores | 2 GB   |
| Build            | 2 min    | 1 core  | 512 MB |
| Integration      | 5 min    | 2 cores | 1 GB   |
| Quality Gate     | 30 sec   | 1 core  | 256 MB |
| Total (parallel) | ~15 min  | -       | -      |

- validates internal documentation links and same-file anchors
- enforces path-safety constraints for link targets
- supports cross-repo policies: `skip`, `warn`, `check`

Primary invocation in CI:

```bash
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```
