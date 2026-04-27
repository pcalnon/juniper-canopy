# Remediation Plan: CI Observability Dependencies

**Date**: 2026-04-04
**Branch**: `fix/ci-test-collection-and-deps`
**Status**: Implemented and Verified
**Related Analysis**: [CI_TEST_FAILURE_ANALYSIS_2026-04-04.md](../history/CI_TEST_FAILURE_ANALYSIS_2026-04-04.md) (archived)

---

## Problem Statement

5 unit tests fail in CI due to undeclared `sentry_sdk` and `prometheus_client` dependencies, blocking the entire CI pipeline.

## Remediation Steps

### Phase 1: Dependency Declaration (Implemented)

**Step 1.1**: Add `observability` optional extra to `pyproject.toml`

```toml
[project.optional-dependencies]
observability = [
    "prometheus-client>=0.20.0",
    "sentry-sdk>=2.0.0",
]
```

- **Strengths**: Proper package metadata; users can opt-in via `pip install juniper-canopy[observability]`
- **Weaknesses**: Adds two new transitive dependency trees
- **Risk**: Low — both are stable, well-maintained packages
- **Guardrails**: Optional extra means base install is unaffected

**Step 1.2**: Add packages to `conf/requirements_ci.txt`

- Added `prometheus-client>=0.20.0` and `sentry-sdk>=2.0.0` in alphabetical order
- Ensures CI environment always has these packages regardless of pip install order

**Step 1.3**: Regenerate `requirements.lock`

```bash
uv pip compile pyproject.toml \
  --extra juniper-data \
  --extra juniper-cascor \
  --extra observability \
  -o requirements.lock
```

- Resolved: `prometheus-client==0.24.1`, `sentry-sdk==2.57.0`
- New transitive dependency: `certifi` now also required by sentry-sdk (already present via requests)

**Step 1.4**: Update CI lockfile freshness check

- Added `--extra observability` to the `uv pip compile` command in `.github/workflows/ci.yml` lockfile check job
- Updated error message to include the new flag

### Phase 2: Verification (Completed)

| Check | Result |
|-------|--------|
| `test_observability.py` (21 tests) | All passed |
| CI-equivalent suite (unit + regression, no slow/server/cascor) | 3389 passed, 0 failed |
| Full test suite | 4169 passed, 56 skipped |
| No tests removed or disabled | Confirmed |
| `requirements.lock` freshness | Matches pyproject.toml |

## Development Roadmap

### Completed

- [x] Identify root cause (undeclared optional dependencies)
- [x] Add `observability` extra to pyproject.toml
- [x] Add packages to CI requirements
- [x] Regenerate requirements.lock
- [x] Update CI lockfile check
- [x] Verify all tests pass locally
- [x] Write analysis document
- [x] Write remediation plan

### Remaining

- [ ] Commit and push changes
- [ ] Verify CI passes on GitHub Actions
- [ ] Create/update PR for merge to main
- [ ] Post-merge: verify main branch CI is green

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New dependency conflicts | Low | Medium | Packages are well-maintained; version pins are flexible |
| Docker image size increase | Low | Low | prometheus-client is ~150KB; sentry-sdk ~2MB |
| Lockfile drift | Low | Low | CI lockfile check now validates the new extra |
