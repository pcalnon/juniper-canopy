# JuniperCanopy Test Suite & CI/CD Enhancement Development Plan

**Version:** 1.0.0  
**Date:** 2026-02-03  
**Author:** AI Agent (Amp)  
**Status:** Draft - Pending Approval  

---

## Executive Summary

This development plan consolidates findings from two independent audit reports (Amp and Claude) and provides a prioritized roadmap for addressing test suite and CI/CD pipeline deficiencies in the JuniperCanopy application.

### Audit Sources

| Report | Auditor | Date | Focus |
|--------|---------|------|-------|
| `TEST_SUITE_AUDIT_CANOPY_AMP.md` | Amp Agent | 2026-02-03 | Test suite quality, CI/CD configuration |
| `TEST_SUITE_AUDIT_CANOPY_CLAUDE.md` | Claude Opus 4.5 | 2026-02-03 | Comprehensive test/CI analysis |

### Consolidated Issue Summary

| Category | Issues Found | Verified |
|----------|--------------|----------|
| Tests Always Pass (`assert True`) | 8 tests | ✅ Verified |
| Non-Test Files in Test Directory | 5 files | ✅ Verified (4 confirmed, 1 partially) |
| Unconditional Skips | 8 tests | ✅ Verified |
| Duplicate conftest.py Files | 2 files (669 lines) | ✅ Verified |
| Overly Permissive Assertions | 10+ tests | ✅ Verified |
| MyPy Error Codes Disabled | 15 codes | ✅ Verified |
| Test Directory Excluded from Linting | 3 tools affected | ✅ Verified |
| Security Scan Errors Suppressed | 2 CI steps | ✅ Verified |

---

## Part 1: Validation of Audit Findings

### 1.1 Cross-Audit Agreement

Both audits independently identified the following **critical issues** with high confidence:

| Issue | Amp Report | Claude Report | Verification Status |
|-------|------------|---------------|---------------------|
| `assert True` in performance tests | 4 tests identified | Same 4 tests | ✅ **VERIFIED** - grep confirms lines 90, 97, 104, 111 |
| `assert True` in integration test | `test_button_state.py:33` | Same location | ✅ **VERIFIED** - grep confirms |
| MyPy with 15 disabled error codes | Lines 148-162 | Same codes listed | ✅ **VERIFIED** - config examined |
| Duplicate conftest.py files | 2 files | 2 files (669 lines total) | ✅ **VERIFIED** - 445 + 224 lines |
| `|| true` in Bandit CI step | Line 412 | Line 412 | ✅ **VERIFIED** - CI file examined |
| Tests excluded from static analysis | flake8, mypy, bandit | Same 3 tools | ✅ **VERIFIED** - pre-commit config |

### 1.2 Divergent Findings Requiring Clarification

| Finding | Amp Report | Claude Report | Resolution |
|---------|------------|---------------|------------|
| Non-test files count | 5 files | 1 file (implementation_script.py) | **Amp is more comprehensive** - Claude missed test_yaml.py, test_dashboard_init.py, test_config.py, test_and_verify_button_layout.py |
| Overly permissive assertions | Not specifically called out | 10+ tests with `in [200, 503]` | **Claude finding validated** - grep confirms pattern exists |
| Duplicate test classes | Not mentioned | test_main_coverage.py vs test_main_coverage_95.py | **Requires further analysis** - files have different purposes (95% coverage target) |

### 1.3 Assumptions Validation

| Assumption | Source | Validation | Result |
|------------|--------|------------|--------|
| Tests contribute to false coverage metrics | Both | `assert True` tests are counted in coverage | ✅ Valid |
| Skipped tests never run in CI | Both | CI uses `-m "not requires_cascor..."` but unconditional skips still skip | ✅ Valid |
| MyPy disabled codes reduce effectiveness | Both | Critical type errors would not be caught | ✅ Valid - industry standard confirms |
| Duplicate fixtures cause confusion | Claude | Both conftest.py files contain similar fixtures | ✅ Valid - same fixtures with minor differences |
| Security scans fail silently | Both | `|| true` suppresses exit code | ✅ Valid |

### 1.4 Logic Validation of Recommendations

| Recommendation | Logic Check | Best Practice Alignment | Approved |
|----------------|-------------|-------------------------|----------|
| Replace `assert True` with real tests | Sound - tests should validate behavior | ✅ Testing best practices | ✅ |
| Move non-test files to util/ | Sound - separation of concerns | ✅ Project organization | ✅ |
| Consolidate conftest.py files | Sound - DRY principle | ✅ pytest best practices | ✅ |
| Re-enable MyPy error codes | Sound - but requires fixing underlying issues | ✅ Type safety | ✅ (phased) |
| Enable linting on tests | Sound - tests are code too | ⚠️ May need relaxed config | ✅ (with adaptation) |
| Remove `|| true` from security | Sound - security should not fail silently | ✅ Security best practices | ✅ |

---

## Part 2: Consolidated Issue Inventory

### 2.1 Test Suite Issues

#### Category A: Tests That Always Pass (8 tests)

| ID | File | Line | Test Name | Issue |
|----|------|------|-----------|-------|
| A1 | `tests/performance/test_button_responsiveness.py` | 90 | `test_rapid_clicking_prevention` | `assert True` |
| A2 | `tests/performance/test_button_responsiveness.py` | 97 | `test_button_disable_during_execution` | `assert True` |
| A3 | `tests/performance/test_button_responsiveness.py` | 104 | `test_button_re_enable_after_timeout` | `assert True` |
| A4 | `tests/performance/test_button_responsiveness.py` | 111 | `test_button_re_enable_after_success` | `assert True` |
| A5 | `tests/integration/test_button_state.py` | 33 | `test_button_click_disables_button` | `assert True` |
| A6 | `tests/unit/frontend/test_metrics_panel_coverage.py` | 373 | `test_add_metrics_with_none` | `assert True` |
| A7 | `tests/unit/test_dashboard_manager.py` | 239 | (exception block) | `assert True` |
| A8 | `tests/unit/test_config_refactoring.py` | 111 | (exception block) | `assert True` |

#### Category B: Non-Test Files in Test Directory (5 files)

| ID | File | Lines | Issue | Recommendation |
|----|------|-------|-------|----------------|
| B1 | `tests/unit/test_yaml.py` | 16 | Print-based script, no assertions | Move to `util/verify_yaml.py` |
| B2 | `tests/unit/test_dashboard_init.py` | 24 | Print-based script, no assertions | Move to `util/verify_dashboard.py` |
| B3 | `tests/unit/test_and_verify_button_layout.py` | 188 | Manual verification script | Move to `util/` |
| B4 | `tests/unit/implementation_script.py` | 460 | Test runner script | Move to `util/` |
| B5 | `tests/integration/test_config.py` | 14 | Print-based script | Move to `util/verify_config.py` |

#### Category C: Unconditional Skips (8 tests)

| ID | File | Line | Test | Skip Reason | Assessment |
|----|------|------|------|-------------|------------|
| C1 | `test_hdf5_snapshots_api.py` | 236 | `test_lists_real_hdf5_files` | Global patching complexity | Valid - technical limitation |
| C2 | `test_hdf5_snapshots_api.py` | 244 | `test_ignores_non_hdf5_files` | Global patching complexity | Valid - technical limitation |
| C3 | `test_main_api_endpoints.py` | 276 | `test_cors_headers_present` | TestClient bypasses CORS | Valid - known limitation |
| C4 | `test_main_api_endpoints.py` | 282 | `test_cors_allows_all_origins` | TestClient bypasses CORS | Valid - known limitation |
| C5 | `test_demo_endpoints.py` | 91 | `test_training_websocket_receives_state_messages` | Async event loop | Questionable - should be e2e |
| C6 | `test_demo_endpoints.py` | 111 | `test_training_websocket_receives_metrics_messages` | Async event loop | Questionable - should be e2e |
| C7 | `test_demo_endpoints.py` | 275 | `test_demo_mode_broadcasts_data` | Async event loop | Questionable - should be e2e |
| C8 | `test_logger_coverage.py` | 134 | `test_verbose_logging` | Feature not implemented | Valid - feature gap |

#### Category D: Duplicate/Redundant Code

| ID | Issue | Files Affected | Impact |
|----|-------|----------------|--------|
| D1 | Duplicate conftest.py fixtures | `tests/conftest.py` (445 lines), `tests/fixtures/conftest.py` (224 lines) | Confusion, maintenance burden |
| D2 | Overlapping test coverage | `test_main_coverage.py` vs `test_main_coverage_95.py` | Duplicate execution |

#### Category E: Logically Weak Tests

| ID | File | Pattern | Issue |
|----|------|---------|-------|
| E1 | `test_main_coverage.py` | `assert response.status_code in [200, 503]` | Accepts server errors as success |
| E2 | `test_network_stats_endpoint.py` | `assert response.status_code in [200, 503]` | Same issue |
| E3 | Multiple files | Tests with `pass` body + skip decorator | Placeholder tests |
| E4 | `test_candidate_visibility.py` | No assertions, print-based | Always passes |

#### Category F: Exception Suppression in Tests

| ID | File | Line | Pattern |
|----|------|------|---------|
| F1 | `test_network_visualizer.py` | 166-167 | `contextlib.suppress(KeyError, ValueError)` |
| F2 | `test_decision_boundary.py` | 178-180 | `contextlib.suppress(ValueError, IndexError)` |
| F3 | `test_button_responsiveness.py` | 63 | `contextlib.suppress(Exception)` |

### 2.2 CI/CD Pipeline Issues

#### Category G: GitHub Actions Issues

| ID | File | Line | Issue | Impact |
|----|------|------|-------|--------|
| G1 | `ci.yml` | 412 | `bandit ... \|\| true` | Security issues fail silently |
| G2 | `ci.yml` | 428 | `pip-audit ... \|\| echo "::warning::"` | Vulnerabilities logged but don't fail |
| G3 | `ci.yml` | 419 | `continue-on-error: true` on SARIF upload | Acceptable for upload |

#### Category H: Pre-commit Configuration Issues

| ID | File | Line | Issue | Impact |
|----|------|------|-------|--------|
| H1 | `.pre-commit-config.yaml` | 134 | Flake8 excludes tests | No linting on test code |
| H2 | `.pre-commit-config.yaml` | 164 | MyPy excludes tests | No type checking on tests |
| H3 | `.pre-commit-config.yaml` | 181 | Bandit excludes tests | Acceptable for tests |
| H4 | `.pre-commit-config.yaml` | 148-162 | 15 MyPy error codes disabled | Type checking ineffective |
| H5 | `.pre-commit-config.yaml` | 126 | Many Flake8 ignores (E722, F401, etc.) | Code quality gaps |
| H6 | `.pre-commit-config.yaml` | 195 | Markdown linting excludes docs/ | Documentation not linted |

#### Category I: Configuration Inconsistencies

| ID | Files | Issue |
|----|-------|-------|
| I1 | `.coveragerc` vs `pyproject.toml` vs `ci.yml` | `fail_under` values differ (60/80/80) |
| I2 | `pyproject.toml` | `-p no:warnings` suppresses all pytest warnings |

---

## Part 3: Prioritized Development Plan

### Priority Classification Criteria

| Priority | Criteria | Timeline |
|----------|----------|----------|
| **P0 - Critical** | False confidence, security risk, data integrity | Immediate (Sprint 1) |
| **P1 - High** | Code quality, maintainability | Sprint 1-2 |
| **P2 - Medium** | Best practices, technical debt | Sprint 2-3 |
| **P3 - Low** | Enhancement, polish | Backlog |

### 3.1 Phase 1: Critical Issues (Sprint 1)

#### Epic 1.1: Eliminate False-Positive Tests

**Objective:** Remove all tests that provide false confidence by always passing.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 1.1.1 Implement real assertions for button performance tests | A1-A4 | 4 hours | 1 day | None |
| 1.1.2 Implement real assertion for button state integration test | A5 | 2 hours | 0.5 day | None |
| 1.1.3 Review and fix exception-block `assert True` patterns | A6-A8 | 2 hours | 0.5 day | None |

**Acceptance Criteria:**
- [ ] Zero `assert True` patterns in test suite
- [ ] All tests actually validate behavior
- [ ] Tests fail when behavior breaks

**Estimated Total:** 8 hours (2 days)

---

#### Epic 1.2: Remove Non-Test Files from Test Directory

**Objective:** Clean up test directory to contain only actual pytest tests.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 1.2.1 Create `util/verification/` directory | - | 0.5 hours | 0.25 day | None |
| 1.2.2 Move test_yaml.py → util/verify_yaml.py | B1 | 0.5 hours | 0.25 day | 1.2.1 |
| 1.2.3 Move test_dashboard_init.py → util/verify_dashboard.py | B2 | 0.5 hours | 0.25 day | 1.2.1 |
| 1.2.4 Move test_config.py → util/verify_config.py | B5 | 0.5 hours | 0.25 day | 1.2.1 |
| 1.2.5 Move test_and_verify_button_layout.py → util/ | B3 | 0.5 hours | 0.25 day | 1.2.1 |
| 1.2.6 Move implementation_script.py → util/ | B4 | 0.5 hours | 0.25 day | 1.2.1 |
| 1.2.7 Update any references to moved files | - | 1 hour | 0.5 day | 1.2.2-1.2.6 |

**Acceptance Criteria:**
- [ ] No non-test Python files in `src/tests/` (except `conftest.py`, `__init__.py`)
- [ ] Verification scripts work from new location
- [ ] Documentation updated

**Estimated Total:** 4 hours (1 day)

---

#### Epic 1.3: Fix Security Scan Suppression in CI

**Objective:** Ensure security issues are properly reported and optionally fail the build.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 1.3.1 Remove `\|\| true` from Bandit step | G1 | 1 hour | 0.5 day | None |
| 1.3.2 Implement proper Bandit failure handling | G1 | 2 hours | 0.5 day | 1.3.1 |
| 1.3.3 Change pip-audit to fail on high severity | G2 | 2 hours | 0.5 day | None |
| 1.3.4 Add security exceptions file for known issues | G1, G2 | 1 hour | 0.25 day | 1.3.2, 1.3.3 |

**Acceptance Criteria:**
- [ ] Security scans fail on actual issues
- [ ] Known/accepted issues are documented in exceptions file
- [ ] CI visibility into security state

**Estimated Total:** 6 hours (1.5 days)

---

### 3.2 Phase 2: High Priority Issues (Sprint 1-2)

#### Epic 2.1: Consolidate conftest.py Files

**Objective:** Single source of truth for test fixtures.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 2.1.1 Audit fixtures in both conftest.py files | D1 | 2 hours | 0.5 day | None |
| 2.1.2 Identify unique fixtures in fixtures/conftest.py | D1 | 1 hour | 0.25 day | 2.1.1 |
| 2.1.3 Merge unique fixtures into tests/conftest.py | D1 | 2 hours | 0.5 day | 2.1.2 |
| 2.1.4 Delete fixtures/conftest.py | D1 | 0.5 hours | 0.25 day | 2.1.3 |
| 2.1.5 Run full test suite to verify no breakage | D1 | 1 hour | 0.5 day | 2.1.4 |

**Acceptance Criteria:**
- [ ] Single conftest.py file
- [ ] All tests pass
- [ ] No duplicate fixture definitions

**Estimated Total:** 6.5 hours (2 days)

---

#### Epic 2.2: Re-enable Critical MyPy Error Codes

**Objective:** Restore meaningful type checking by fixing type issues and re-enabling codes.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 2.2.1 Run MyPy with `arg-type` enabled, capture errors | H4 | 1 hour | 0.25 day | None |
| 2.2.2 Fix `arg-type` errors in codebase | H4 | 8 hours | 2 days | 2.2.1 |
| 2.2.3 Enable `arg-type` in pre-commit config | H4 | 0.5 hours | 0.25 day | 2.2.2 |
| 2.2.4 Run MyPy with `return-value` enabled, capture errors | H4 | 1 hour | 0.25 day | 2.2.3 |
| 2.2.5 Fix `return-value` errors in codebase | H4 | 6 hours | 1.5 days | 2.2.4 |
| 2.2.6 Enable `return-value` in pre-commit config | H4 | 0.5 hours | 0.25 day | 2.2.5 |
| 2.2.7 Run MyPy with `assignment` enabled, capture errors | H4 | 1 hour | 0.25 day | 2.2.6 |
| 2.2.8 Fix `assignment` errors in codebase | H4 | 4 hours | 1 day | 2.2.7 |
| 2.2.9 Enable `assignment` in pre-commit config | H4 | 0.5 hours | 0.25 day | 2.2.8 |

**Acceptance Criteria:**
- [ ] Three critical MyPy codes re-enabled: `arg-type`, `return-value`, `assignment`
- [ ] No MyPy errors in pre-commit
- [ ] CI passes with new config

**Estimated Total:** 22.5 hours (6 days)

---

#### Epic 2.3: Enable Linting on Test Files

**Objective:** Apply code quality standards to test code.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 2.3.1 Create relaxed flake8 config for tests | H1 | 2 hours | 0.5 day | None |
| 2.3.2 Run flake8 on tests with relaxed config, capture issues | H1 | 1 hour | 0.25 day | 2.3.1 |
| 2.3.3 Fix critical flake8 issues in tests (E722, B008) | H1 | 4 hours | 1 day | 2.3.2 |
| 2.3.4 Remove test exclusion from flake8 pre-commit | H1 | 0.5 hours | 0.25 day | 2.3.3 |
| 2.3.5 Create relaxed mypy config for tests | H2 | 2 hours | 0.5 day | None |
| 2.3.6 Remove test exclusion from mypy pre-commit | H2 | 0.5 hours | 0.25 day | 2.3.5 |

**Acceptance Criteria:**
- [ ] Tests pass flake8 with relaxed config
- [ ] Tests pass mypy with relaxed config
- [ ] Pre-commit hooks apply to test files

**Estimated Total:** 10 hours (3 days)

---

### 3.3 Phase 3: Medium Priority Issues (Sprint 2-3)

#### Epic 3.1: Fix Logically Weak Tests

**Objective:** Strengthen test assertions to catch real issues.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 3.1.1 Identify tests with `in [200, 503]` pattern | E1, E2 | 1 hour | 0.25 day | None |
| 3.1.2 Analyze expected behavior for each endpoint | E1, E2 | 2 hours | 0.5 day | 3.1.1 |
| 3.1.3 Tighten assertions to specific expected codes | E1, E2 | 4 hours | 1 day | 3.1.2 |
| 3.1.4 Add assertions to test_candidate_visibility.py | E4 | 2 hours | 0.5 day | None |
| 3.1.5 Remove or implement placeholder tests | E3 | 2 hours | 0.5 day | None |

**Acceptance Criteria:**
- [ ] No tests accept 500-level errors as success
- [ ] All tests have meaningful assertions
- [ ] Placeholder tests removed or implemented

**Estimated Total:** 11 hours (3 days)

---

#### Epic 3.2: Address Unconditional Skips

**Objective:** Either fix skipped tests or document why they must remain skipped.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 3.2.1 Analyze WebSocket test async compatibility | C5, C6, C7 | 4 hours | 1 day | None |
| 3.2.2 Implement async-compatible WebSocket tests or move to e2e | C5, C6, C7 | 8 hours | 2 days | 3.2.1 |
| 3.2.3 Document remaining valid skips with ADR | C1-C4, C8 | 2 hours | 0.5 day | None |

**Acceptance Criteria:**
- [ ] WebSocket tests either run or are in e2e category
- [ ] All skips have documented justification
- [ ] Skip count reduced where possible

**Estimated Total:** 14 hours (3.5 days)

---

#### Epic 3.3: Fix Exception Suppression in Tests

**Objective:** Tests should not silently swallow exceptions.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 3.3.1 Identify all `contextlib.suppress` usage in tests | F1-F3 | 1 hour | 0.25 day | None |
| 3.3.2 Replace with explicit exception handling and assertions | F1-F3 | 4 hours | 1 day | 3.3.1 |

**Acceptance Criteria:**
- [ ] No `contextlib.suppress(Exception)` in tests
- [ ] Tests explicitly verify expected exceptions

**Estimated Total:** 5 hours (1.25 days)

---

#### Epic 3.4: Re-enable Additional Flake8 Checks

**Objective:** Catch more code quality issues.

| Task | Issue IDs | Effort | Duration | Dependencies |
|------|-----------|--------|----------|--------------|
| 3.4.1 Re-enable F401 (unused imports), fix issues | H5 | 4 hours | 1 day | None |
| 3.4.2 Re-enable E722 (bare except), fix issues | H5 | 4 hours | 1 day | None |
| 3.4.3 Re-enable B008 (mutable default), fix issues | H5 | 2 hours | 0.5 day | None |

**Acceptance Criteria:**
- [ ] F401, E722, B008 enabled
- [ ] No violations in codebase
- [ ] CI passes

**Estimated Total:** 10 hours (2.5 days)

---

### 3.4 Phase 4: Low Priority Issues (Backlog)

#### Epic 4.1: Configuration Standardization

| Task | Issue IDs | Effort | Duration |
|------|-----------|--------|----------|
| 4.1.1 Standardize coverage fail_under to 80% everywhere | I1 | 1 hour | 0.25 day |
| 4.1.2 Re-enable pytest warnings, address issues | I2 | 4 hours | 1 day |

**Estimated Total:** 5 hours (1.25 days)

---

#### Epic 4.2: Documentation and Remaining Cleanup

| Task | Issue IDs | Effort | Duration |
|------|-----------|--------|----------|
| 4.2.1 Enable markdown linting for docs/ | H6 | 2 hours | 0.5 day |
| 4.2.2 Document test directory structure | - | 2 hours | 0.5 day |
| 4.2.3 Audit duplicate test classes | D2 | 4 hours | 1 day |

**Estimated Total:** 8 hours (2 days)

---

#### Epic 4.3: Future MyPy Improvements

| Task | Issue IDs | Effort | Duration |
|------|-----------|--------|----------|
| 4.3.1 Assess remaining MyPy disabled codes | H4 | 2 hours | 0.5 day |
| 4.3.2 Incrementally enable additional codes | H4 | 16 hours | 4 days |

**Estimated Total:** 18 hours (4.5 days)

---

## Part 4: Effort Summary and Timeline

### 4.1 Effort by Phase

| Phase | Epics | Estimated Hours | Estimated Days |
|-------|-------|-----------------|----------------|
| Phase 1: Critical | 1.1, 1.2, 1.3 | 18 hours | 4.5 days |
| Phase 2: High | 2.1, 2.2, 2.3 | 39 hours | 11 days |
| Phase 3: Medium | 3.1, 3.2, 3.3, 3.4 | 40 hours | 10.25 days |
| Phase 4: Low | 4.1, 4.2, 4.3 | 31 hours | 7.75 days |
| **TOTAL** | **15 Epics** | **128 hours** | **33.5 days** |

### 4.2 Recommended Sprint Allocation

| Sprint | Focus | Epics | Target Completion |
|--------|-------|-------|-------------------|
| Sprint 1 | Critical issues, start high priority | 1.1, 1.2, 1.3, 2.1 | Week 2 |
| Sprint 2 | Complete high priority | 2.2, 2.3 | Week 4 |
| Sprint 3 | Medium priority | 3.1, 3.2, 3.3, 3.4 | Week 6 |
| Sprint 4 | Low priority, cleanup | 4.1, 4.2, 4.3 | Week 8 |

### 4.3 Resource Requirements

| Role | Allocation | Sprints |
|------|------------|---------|
| Senior Developer | 80% | All |
| QA Engineer | 40% | Sprint 1-3 |
| DevOps Engineer | 20% | Sprint 1-2 |

---

## Part 5: Risk Assessment

### 5.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| MyPy fixes break existing functionality | Medium | High | Comprehensive testing, phased rollout |
| Moving files breaks import paths | Low | Medium | Update all references, test thoroughly |
| Stricter linting slows development | Medium | Low | Gradual enforcement, clear documentation |
| Security fixes reveal new vulnerabilities | Medium | Medium | Address in priority order |

### 5.2 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| MyPy fixes take longer than estimated | High | Medium | Buffer time built into Phase 2 |
| Integration with Cascor work creates conflicts | Medium | Medium | Coordinate with integration team |
| Unforeseen test failures after changes | Medium | Low | Thorough testing at each epic completion |

---

## Part 6: Success Metrics

### 6.1 Quality Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Tests with `assert True` | 8 | 0 | Sprint 1 |
| Non-test files in test dir | 5 | 0 | Sprint 1 |
| Unconditional skips | 8 | ≤3 (with documentation) | Sprint 3 |
| MyPy disabled error codes | 15 | ≤10 | Sprint 2 |
| Flake8 ignored categories | 14 | ≤10 | Sprint 3 |

### 6.2 CI/CD Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Security scans with silent failures | 2 | 0 | Sprint 1 |
| Coverage threshold consistency | 60/80/80 | 80/80/80 | Sprint 4 |
| Pre-commit coverage of tests | Excluded | Included | Sprint 2 |

---

## Appendix A: Quick Reference - Issue-to-Task Mapping

| Issue ID | Task ID(s) | Priority | Status |
|----------|------------|----------|--------|
| A1-A4 | 1.1.1 | P0 | Pending |
| A5 | 1.1.2 | P0 | Pending |
| A6-A8 | 1.1.3 | P0 | Pending |
| B1-B5 | 1.2.1-1.2.7 | P0 | Pending |
| C1-C8 | 3.2.1-3.2.3 | P2 | Pending |
| D1 | 2.1.1-2.1.5 | P1 | Pending |
| D2 | 4.2.3 | P3 | Pending |
| E1-E4 | 3.1.1-3.1.5 | P2 | Pending |
| F1-F3 | 3.3.1-3.3.2 | P2 | Pending |
| G1-G2 | 1.3.1-1.3.4 | P0 | Pending |
| H1-H2 | 2.3.1-2.3.6 | P1 | Pending |
| H4 | 2.2.1-2.2.9 | P1 | Pending |
| H5 | 3.4.1-3.4.3 | P2 | Pending |
| H6 | 4.2.1 | P3 | Pending |
| I1-I2 | 4.1.1-4.1.2 | P3 | Pending |

---

## Appendix B: Implementation Checklist Template

### Phase 1 Completion Checklist

- [ ] Epic 1.1: All `assert True` patterns eliminated
- [ ] Epic 1.2: All non-test files moved to `util/`
- [ ] Epic 1.3: Security scans fail appropriately on issues
- [ ] All Phase 1 tests pass
- [ ] Pre-commit hooks pass
- [ ] CI pipeline green

### Phase 2 Completion Checklist

- [ ] Epic 2.1: Single conftest.py file
- [ ] Epic 2.2: Three MyPy codes re-enabled
- [ ] Epic 2.3: Linting enabled on tests
- [ ] All tests pass
- [ ] No regressions from Phase 1
- [ ] CI pipeline green

---

*End of Development Plan*
