# JuniperCanopy Test Suite & CI/CD Enhancement Development Plan

**Version:** 1.1.0
**Date:** 2026-02-04
**Last Updated:** 2026-02-04
**Authors:** AI Agents (Amp, Claude Opus 4.5) - Consolidated
**Source Audits:** TEST_SUITE_AUDIT_CANOPY_AMP.md, TEST_SUITE_AUDIT_CANOPY_CLAUDE.md
**Status:** Phase 1 Complete - In Progress

## Implementation Status

| Phase   | Description                  | Status         | Completion Date |
| ------- | ---------------------------- | -------------- | --------------- |
| Phase 1 | Critical Issues              | ✅ Complete     | 2026-02-04      |
| Phase 2 | High Priority                | 🔲 Pending      | -               |
| Phase 3 | Medium Priority              | 🔲 Pending      | -               |
| Phase 4 | Low Priority / Tech Debt     | 🔲 Pending      | -               |

### Phase 1 Summary (Complete)
- **Epic 1.1**: Eliminated all 9 `assert True` false-positive test patterns
- **Epic 1.2**: Moved 5 non-test files from test directory to `util/verification/`
- **Epic 1.3**: Fixed security scan suppression in CI (Bandit, pip-audit)

---

## Executive Summary

This development plan consolidates findings from two independent test suite audits and provides a comprehensive, prioritized roadmap for addressing test suite and CI/CD pipeline deficiencies in the JuniperCanopy application.

### Audit Sources

| Report                              | Auditor         | Date       | Focus                                   |
| ----------------------------------- | --------------- | ---------- | --------------------------------------- |
| `TEST_SUITE_AUDIT_CANOPY_AMP.md`    | Amp Agent       | 2026-02-03 | Test suite quality, CI/CD configuration |
| `TEST_SUITE_AUDIT_CANOPY_CLAUDE.md` | Claude Opus 4.5 | 2026-02-03 | Comprehensive test/CI analysis          |

### Consolidated Issue Summary

| Category                             | Critical | High   | Medium | Low     | Total   |
| ------------------------------------ | -------- | ------ | ------ | ------- | ------- |
| False-Positive Tests (`assert True`) | 1        | 7      | 1      | 0       | **9**   |
| Non-Test Files in Test Directory     | 0        | 5      | 0      | 0       | **5**   |
| Unconditional Skips                  | 0        | 0      | 9      | 0       | **9**   |
| Exception Suppression                | 0        | 0      | 0      | 25+     | **25+** |
| Duplicate conftest.py Files          | 0        | 1      | 0      | 0       | **1**   |
| Overly Permissive Assertions         | 0        | 0      | 3      | 0       | **3**   |
| MyPy Error Codes Disabled            | 0        | 1      | 0      | 0       | **1**   |
| Test Directory Excluded from Linting | 0        | 3      | 0      | 0       | **3**   |
| Security Scan Errors Suppressed      | 0        | 0      | 2      | 0       | **2**   |
| Configuration Inconsistencies        | 0        | 0      | 1      | 2       | **3**   |
| Duplicate Test Classes               | 0        | 0      | 1      | 0       | **1**   |
| **TOTAL**                            | **1**    | **17** | **17** | **27+** | **62+** |

### Estimated Total Effort

| Phase             | Description              | Estimated Hours | Estimated Days | Sprint(s)     |
| ----------------- | ------------------------ | --------------- | -------------- | ------------- |
| Phase 1: Critical | Critical & High Priority | 18 hours        | 4.5 days       | Sprint 1      |
| Phase 2: High     | High Priority Completion | 39 hours        | 11 days        | Sprint 1-2    |
| Phase 3: Medium   | Medium Priority          | 40 hours        | 10.25 days     | Sprint 2-3    |
| Phase 4: Low      | Low Priority / Tech Debt | 31 hours        | 7.75 days      | Sprint 3+     |
| **TOTAL**         | **15 Epics**             | **128 hours**   | **33.5 days**  | **4 Sprints** |

---

## Table of Contents

1. [Audit Comparison & Validation](#1-audit-comparison--validation)
2. [Consolidated Issue Catalog](#2-consolidated-issue-catalog)
3. [Development Plan - Phase 1 (Critical)](#3-development-plan---phase-1-critical)
4. [Development Plan - Phase 2 (High)](#4-development-plan---phase-2-high)
5. [Development Plan - Phase 3 (Medium)](#5-development-plan---phase-3-medium)
6. [Development Plan - Phase 4 (Low/Tech Debt)](#6-development-plan---phase-4-lowtech-debt)
7. [Effort Summary and Timeline](#7-effort-summary-and-timeline)
8. [Risk Assessment](#8-risk-assessment)
9. [Success Metrics](#9-success-metrics)
10. [Implementation Guidelines](#10-implementation-guidelines)
11. [Verification Checklist](#11-verification-checklist)
12. [Appendix A: Issue-to-Task Mapping](#appendix-a-issue-to-task-mapping)
13. [Appendix B: File-by-File Action Items](#appendix-b-file-by-file-action-items)
14. [Appendix C: Implementation Checklist Template](#appendix-c-implementation-checklist-template)

---

## 1. Audit Comparison & Validation

### 1.1 Cross-Audit Agreement

Both audits independently identified the following **critical issues** with high confidence:

| Issue                               | Amp Report                | Claude Report             | Verification Status                                    |
| ----------------------------------- | ------------------------- | ------------------------- | ------------------------------------------------------ |
| `assert True` in performance tests  | 4 tests identified        | Same 4 tests              | ✅ **VERIFIED** - grep confirms lines 90, 97, 104, 111 |
| `assert True` in integration test   | `test_button_state.py:33` | Same location             | ✅ **VERIFIED** - grep confirms                        |
| MyPy with 15 disabled error codes   | Lines 148-162             | Same codes listed         | ✅ **VERIFIED** - config examined                      |
| Duplicate conftest.py files         | 2 files                   | 2 files (669 lines total) | ✅ **VERIFIED** - 445 + 224 lines                      |
| `\|\| true` in Bandit CI step       | Line 412                  | Line 412                  | ✅ **VERIFIED** - CI file examined                     |
| Tests excluded from static analysis | flake8, mypy, bandit      | Same 3 tools              | ✅ **VERIFIED** - pre-commit config                    |
| pip-audit warnings only             | Line 428                  | Line 428                  | ✅ **VERIFIED** - CI file examined                     |

### 1.2 Additional Findings by AMP

AMP identified these issues not fully addressed in Claude audit:

| Finding                          | Location                                                                               | Validation Status                                            |
| -------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 4 additional non-test files      | test_yaml.py, test_config.py, test_dashboard_init.py, test_and_verify_button_layout.py | **CONFIRMED** - All are manual scripts with print statements |
| Coverage threshold inconsistency | .coveragerc (60%) vs pyproject.toml (80%)                                              | **CONFIRMED** - Values differ                                |
| Pytest warnings suppressed       | pyproject.toml `-p no:warnings`                                                        | **CONFIRMED** - Line 148                                     |
| contextlib.suppress usage        | Multiple test files                                                                    | **CONFIRMED** - Found 25+ instances                          |

### 1.3 Additional Findings by Claude

Claude identified these issues not fully addressed in AMP audit:

| Finding                             | Location                   | Validation Status                                             |
| ----------------------------------- | -------------------------- | ------------------------------------------------------------- |
| Duplicate test classes              | test_main_coverage_95.py   | **CONFIRMED** - Duplicates classes from test_main_coverage.py |
| Overly permissive status assertions | Multiple files             | **CONFIRMED** - `assert status in [200, 400, 500]` patterns   |
| Tests documenting bugs              | test_logger_coverage_95.py | **CONFIRMED** - Uses pytest.raises for expected bugs          |

### 1.4 Divergent Findings Requiring Clarification

| Finding                      | Amp Report                  | Claude Report                                     | Resolution                                                                                                                           |
| ---------------------------- | --------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Non-test files count         | 5 files                     | 1 file (implementation_script.py)                 | **Amp is more comprehensive** - Claude missed test_yaml.py, test_dashboard_init.py, test_config.py, test_and_verify_button_layout.py |
| Overly permissive assertions | Not specifically called out | 10+ tests with `in [200, 503]`                    | **Claude finding validated** - grep confirms pattern exists                                                                          |
| Duplicate test classes       | Not mentioned               | test_main_coverage.py vs test_main_coverage_95.py | **Requires further analysis** - files have different purposes (95% coverage target)                                                  |

### 1.5 Assumptions Validation

| Assumption                                 | Source | Validation                                                               | Result                                          |
| ------------------------------------------ | ------ | ------------------------------------------------------------------------ | ----------------------------------------------- |
| Tests contribute to false coverage metrics | Both   | `assert True` tests are counted in coverage                              | ✅ Valid                                        |
| Skipped tests never run in CI              | Both   | CI uses `-m "not requires_cascor..."` but unconditional skips still skip | ✅ Valid                                        |
| MyPy disabled codes reduce effectiveness   | Both   | Critical type errors would not be caught                                 | ✅ Valid - industry standard confirms           |
| Duplicate fixtures cause confusion         | Claude | Both conftest.py files contain similar fixtures                          | ✅ Valid - same fixtures with minor differences |
| Security scans fail silently               | Both   | `\|\| true` suppresses exit code                                         | ✅ Valid                                        |

### 1.6 Logic Validation of Recommendations

| Recommendation                        | Logic Check                                   | Best Practice Alignment      | Approved             |
| ------------------------------------- | --------------------------------------------- | ---------------------------- | -------------------- |
| Replace `assert True` with real tests | Sound - tests should validate behavior        | ✅ Testing best practices    | ✅                   |
| Move non-test files to util/          | Sound - separation of concerns                | ✅ Project organization      | ✅                   |
| Consolidate conftest.py files         | Sound - DRY principle                         | ✅ pytest best practices     | ✅                   |
| Re-enable MyPy error codes            | Sound - but requires fixing underlying issues | ✅ Type safety               | ✅ (phased)          |
| Enable linting on tests               | Sound - tests are code too                    | ⚠️ May need relaxed config   | ✅ (with adaptation) |
| Remove `\|\| true` from security      | Sound - security should not fail silently     | ✅ Security best practices   | ✅                   |

### 1.7 Validation Methodology

All findings were validated through:

1. Direct file reading to confirm issue existence
2. Grep pattern matching for issue patterns (`assert True`, `contextlib.suppress`, etc.)
3. Configuration file cross-referencing
4. Best practices comparison against pytest, CI/CD, and Python community standards

---

## 2. Consolidated Issue Catalog

### 2.1 Tests That Always Pass (`assert True`)

**Impact:** These tests inflate coverage metrics while providing zero verification. Code changes breaking tested functionality would not be detected.

| ID     | AMP ID | File                                                 | Test/Line                                 | Issue                                | Severity |
| ------ | ------ | ---------------------------------------------------- | ----------------------------------------- | ------------------------------------ | -------- |
| FP-001 | A1     | `tests/performance/test_button_responsiveness.py`    | `test_rapid_clicking_prevention`:90       | `assert True`                        | CRITICAL |
| FP-002 | A2     | `tests/performance/test_button_responsiveness.py`    | `test_button_disable_during_execution`:97 | `assert True`                        | HIGH     |
| FP-003 | A3     | `tests/performance/test_button_responsiveness.py`    | `test_button_re_enable_after_timeout`:104 | `assert True`                        | HIGH     |
| FP-004 | A4     | `tests/performance/test_button_responsiveness.py`    | `test_button_re_enable_after_success`:111 | `assert True`                        | HIGH     |
| FP-005 | A5     | `tests/integration/test_button_state.py`             | `test_button_click_disables_button`:33    | `assert True`                        | HIGH     |
| FP-006 | A6     | `tests/unit/frontend/test_metrics_panel_coverage.py` | `test_add_metrics_with_none`:373          | `assert True`                        | HIGH     |
| FP-007 | A7     | `tests/unit/test_dashboard_manager.py`               | (exception block):239                     | `assert True` in except block        | HIGH     |
| FP-008 | A8     | `tests/unit/test_config_refactoring.py`              | (exception block):111                     | `assert True`                        | HIGH     |
| FP-009 | -      | `tests/regression/test_candidate_visibility.py`      | Entire file                               | No assertions, only print statements | MEDIUM   |

### 2.2 Non-Test Files in Test Directory

**Impact:** Files contribute to test metrics but provide no automated verification. May confuse pytest collection and inflate test counts.

| ID      | AMP ID | File                                          | Lines | Issue                                                | Recommendation                     |
| ------- | ------ | --------------------------------------------- | ----- | ---------------------------------------------------- | ---------------------------------- |
| NTF-001 | B1     | `tests/unit/test_yaml.py`                     | 16    | Manual script with try/except and print statements   | Move to `util/verify_yaml.py`      |
| NTF-002 | B2     | `tests/unit/test_dashboard_init.py`           | 24    | Manual verification script with print statements     | Move to `util/verify_dashboard.py` |
| NTF-003 | B3     | `tests/unit/test_and_verify_button_layout.py` | 188   | Manual verification with `if __name__ == "__main__"` | Move to `util/`                    |
| NTF-004 | B4     | `tests/unit/implementation_script.py`         | 460   | Test runner script with global variables             | Move to `util/`                    |
| NTF-005 | B5     | `tests/integration/test_config.py`            | 14    | Print-based script                                   | Move to `util/verify_config.py`    |

### 2.3 Unconditional Skips

**Impact:** Tests never execute in CI, providing false sense of coverage.

| ID     | AMP ID | File                            | Line | Test                                                | Skip Reason                  | Assessment                           |
| ------ | ------ | ------------------------------- | ---- | --------------------------------------------------- | ---------------------------- | ------------------------------------ |
| SK-001 | C1     | `test_hdf5_snapshots_api.py`    | 236  | `test_lists_real_hdf5_files`                        | Global patching complexity   | Valid - Technical limitation         |
| SK-002 | C2     | `test_hdf5_snapshots_api.py`    | 244  | `test_ignores_non_hdf5_files`                       | Global patching complexity   | Valid - Technical limitation         |
| SK-003 | C3     | `test_main_api_endpoints.py`    | 276  | `test_cors_headers_present`                         | TestClient bypasses CORS     | Valid - Known limitation             |
| SK-004 | C4     | `test_main_api_endpoints.py`    | 282  | `test_cors_allows_all_origins`                      | TestClient bypasses CORS     | Valid - Known limitation             |
| SK-005 | C5     | `test_demo_endpoints.py`        | 91   | `test_training_websocket_receives_state_messages`   | Async event loop             | Questionable - Should convert to e2e |
| SK-006 | C6     | `test_demo_endpoints.py`        | 111  | `test_training_websocket_receives_metrics_messages` | Async event loop             | Questionable - Should convert to e2e |
| SK-007 | C7     | `test_demo_endpoints.py`        | 275  | `test_demo_mode_broadcasts_data`                    | Async event loop             | Questionable - Should convert to e2e |
| SK-008 | C8     | `test_logger_coverage.py`       | 134  | `test_verbose_logging`                              | Custom level not implemented | Valid - Feature gap                  |
| SK-009 | -      | `test_parameter_persistence.py` | -    | `test_api_set_params_integration`                   | Requires running server      | Questionable - Should be e2e         |

### 2.4 Duplicate/Redundant Code

**Impact:** Maintenance burden, confusion about authoritative source.

| ID     | AMP ID | Issue                          | Files Affected                                                            | Impact                                |
| ------ | ------ | ------------------------------ | ------------------------------------------------------------------------- | ------------------------------------- |
| DUP-01 | D1     | Duplicate conftest.py fixtures | `tests/conftest.py` (445 lines), `tests/fixtures/conftest.py` (224 lines) | Confusion, maintenance burden         |
| DUP-02 | D2     | Overlapping test coverage      | `test_main_coverage.py` vs `test_main_coverage_95.py`                     | Duplicate execution, 5 classes shared |

### 2.5 Logically Weak Tests

**Impact:** Tests pass even when behavior is wrong.

| ID     | AMP ID | File                             | Pattern                                     | Issue                                 |
| ------ | ------ | -------------------------------- | ------------------------------------------- | ------------------------------------- |
| LW-001 | E1     | `test_main_coverage.py`          | `assert response.status_code in [200, 503]` | Accepts server errors as success      |
| LW-002 | E2     | `test_network_stats_endpoint.py` | `assert response.status_code in [200, 503]` | Same issue                            |
| LW-003 | E3     | Multiple files                   | Tests with `pass` body + skip decorator     | Placeholder tests                     |
| LW-004 | E4     | `test_candidate_visibility.py`   | No assertions, print-based                  | Always passes (also listed as FP-009) |

### 2.6 Exception Suppression in Tests

**Impact:** Tests silently swallow exceptions that might indicate failures.

| ID     | AMP ID | File                            | Line    | Pattern                                       |
| ------ | ------ | ------------------------------- | ------- | --------------------------------------------- |
| EXC-01 | F1     | `test_network_visualizer.py`    | 166-167 | `contextlib.suppress(KeyError, ValueError)`   |
| EXC-02 | F2     | `test_decision_boundary.py`     | 178-180 | `contextlib.suppress(ValueError, IndexError)` |
| EXC-03 | F3     | `test_button_responsiveness.py` | 63      | `contextlib.suppress(Exception)`              |
| EXC-04 | -      | Multiple test files             | Various | 25+ total instances                           |

### 2.7 CI/CD Configuration Issues

#### GitHub Actions Issues

| ID     | AMP ID | File     | Line | Issue                                     | Impact                                |
| ------ | ------ | -------- | ---- | ----------------------------------------- | ------------------------------------- |
| CI-001 | G1     | `ci.yml` | 412  | `bandit ... \|\| true`                    | Security issues fail silently         |
| CI-002 | G2     | `ci.yml` | 428  | `pip-audit ... \|\| echo "::warning::"`   | Vulnerabilities logged but don't fail |
| CI-003 | G3     | `ci.yml` | 419  | `continue-on-error: true` on SARIF upload | Acceptable for upload                 |

#### Pre-commit Configuration Issues

| ID     | AMP ID | File                      | Line    | Issue                                  | Impact                    |
| ------ | ------ | ------------------------- | ------- | -------------------------------------- | ------------------------- |
| PC-001 | H1     | `.pre-commit-config.yaml` | 134     | Flake8 excludes tests                  | No linting on test code   |
| PC-002 | H2     | `.pre-commit-config.yaml` | 164     | MyPy excludes tests                    | No type checking on tests |
| PC-003 | H3     | `.pre-commit-config.yaml` | 181     | Bandit excludes tests                  | Acceptable for tests      |
| PC-004 | H4     | `.pre-commit-config.yaml` | 148-162 | 15 MyPy error codes disabled           | Type checking ineffective |
| PC-005 | H5     | `.pre-commit-config.yaml` | 126     | Many Flake8 ignores (E722, F401, etc.) | Code quality gaps         |
| PC-006 | H6     | `.pre-commit-config.yaml` | 195     | Markdown linting excludes docs/        | Documentation not linted  |

#### Configuration Inconsistencies

| ID     | AMP ID | Files                                         | Issue                                           |
| ------ | ------ | --------------------------------------------- | ----------------------------------------------- |
| CFG-01 | I1     | `.coveragerc` vs `pyproject.toml` vs `ci.yml` | `fail_under` values differ (60/80/80)           |
| CFG-02 | I2     | `pyproject.toml`                              | `-p no:warnings` suppresses all pytest warnings |

### 2.8 Code Quality Issues in Tests

| ID     | Category                   | Files Affected               | Instance Count | Severity |
| ------ | -------------------------- | ---------------------------- | -------------- | -------- |
| CQ-001 | Tests documenting bugs     | test_logger_coverage_95.py   | 2              | MEDIUM   |
| CQ-002 | Misleading test docstrings | test_max_epochs_parameter.py | 2              | LOW      |

---

## 3. Development Plan - Phase 1 (Critical)

**Timeline:** Sprint 1 (Week 1-2)
**Priority:** Critical issues that cause false confidence
**Goal:** Eliminate false-positive tests and major CI/CD gaps

### Epic 1.1: Eliminate False-Positive Tests

**Objective:** Remove all tests that provide false confidence by always passing.

| Task  | Issue IDs        | File                           | Action                                                                           | Effort  | Duration | Dependencies |
| ----- | ---------------- | ------------------------------ | -------------------------------------------------------------------------------- | ------- | -------- | ------------ |
| 1.1.1 | FP-001 to FP-004 | test_button_responsiveness.py  | Implement real button behavior tests using Dash test utilities or mock callbacks | 4 hours | 1 day    | None         |
| 1.1.2 | FP-005           | test_button_state.py           | Implement actual button state verification                                       | 2 hours | 0.5 day  | None         |
| 1.1.3 | FP-006           | test_metrics_panel_coverage.py | Replace `assert True` with proper metrics validation                             | 1 hour  | 0.25 day | None         |
| 1.1.4 | FP-007, FP-008   | Various                        | Replace exception-block `assert True` with proper error testing                  | 2 hours | 0.5 day  | None         |
| 1.1.5 | FP-009           | test_candidate_visibility.py   | Add `assert` statements for visibility checks                                    | 2 hours | 0.5 day  | None         |

**Example Fix for test_button_responsiveness.py:**

```python
# BEFORE (Always passes)
def test_rapid_clicking_prevention(self):
    assert True  # Debouncing is implemented

# AFTER (Actually tests behavior)
def test_rapid_clicking_prevention(self):
    """Test that rapid clicking does not send duplicate commands."""
    from unittest.mock import Mock, patch

    # Mock the WebSocket manager
    with patch('frontend.components.websocket_manager') as mock_ws:
        callback = handle_training_buttons

        # Simulate rapid clicks
        for _ in range(5):
            callback(1, None, None, 'Start')

        # Verify only one command was sent (debouncing worked)
        assert mock_ws.send_command.call_count == 1
```

**Acceptance Criteria:**

- [ ] Zero `assert True` patterns in test suite
- [ ] All tests actually validate behavior
- [ ] Tests fail when behavior breaks

**Estimated Total:** 11 hours (2.75 days)

---

### Epic 1.2: Remove Non-Test Files from Test Directory

**Objective:** Clean up test directory to contain only actual pytest tests.

| Task  | Issue IDs | Source File                                 | Destination                           | Effort    | Duration | Dependencies |
| ----- | --------- | ------------------------------------------- | ------------------------------------- | --------- | -------- | ------------ |
| 1.2.1 | -         | -                                           | Create `util/verification/` directory | 0.5 hours | 0.25 day | None         |
| 1.2.2 | NTF-001   | tests/unit/test_yaml.py                     | util/verify_yaml.py                   | 0.5 hours | 0.25 day | 1.2.1        |
| 1.2.3 | NTF-002   | tests/unit/test_dashboard_init.py           | util/verify_dashboard.py              | 0.5 hours | 0.25 day | 1.2.1        |
| 1.2.4 | NTF-005   | tests/integration/test_config.py            | util/verify_config.py                 | 0.5 hours | 0.25 day | 1.2.1        |
| 1.2.5 | NTF-003   | tests/unit/test_and_verify_button_layout.py | util/verify_button_layout.py          | 0.5 hours | 0.25 day | 1.2.1        |
| 1.2.6 | NTF-004   | tests/unit/implementation_script.py         | util/implementation_script.py         | 0.5 hours | 0.25 day | 1.2.1        |
| 1.2.7 | -         | Various                                     | Update any references to moved files  | 1 hour    | 0.5 day  | 1.2.2-1.2.6  |

**Commands:**

```bash
# Execute file moves
git mv src/tests/unit/test_yaml.py util/verify_yaml.py
git mv src/tests/unit/test_dashboard_init.py util/verify_dashboard.py
git mv src/tests/unit/test_and_verify_button_layout.py util/verify_button_layout.py
git mv src/tests/unit/implementation_script.py util/implementation_script.py
git mv src/tests/integration/test_config.py util/verify_config_integration.py
```

**Acceptance Criteria:**

- [ ] No non-test Python files in `src/tests/` (except `conftest.py`, `__init__.py`)
- [ ] Verification scripts work from new location
- [ ] Documentation updated

**Estimated Total:** 4 hours (1 day)

---

### Epic 1.3: Fix Security Scan Suppression in CI

**Objective:** Ensure security issues are properly reported and optionally fail the build.

| Task  | Issue IDs      | File    | Line | Action                                        | Effort  | Duration | Dependencies |
| ----- | -------------- | ------- | ---- | --------------------------------------------- | ------- | -------- | ------------ |
| 1.3.1 | CI-001         | ci.yml  | 412  | Remove `\|\| true` from Bandit command        | 1 hour  | 0.5 day  | None         |
| 1.3.2 | CI-001         | ci.yml  | -    | Implement proper Bandit failure handling      | 2 hours | 0.5 day  | 1.3.1        |
| 1.3.3 | CI-002         | ci.yml  | 428  | Change pip-audit to fail on high severity     | 2 hours | 0.5 day  | None         |
| 1.3.4 | CI-001, CI-002 | Various | -    | Add security exceptions file for known issues | 1 hour  | 0.25 day | 1.3.2, 1.3.3 |

**Updated CI Configuration:**

```yaml
# BEFORE
bandit -r src -f sarif -o reports/security/bandit.sarif || true

# AFTER
bandit -r src -f sarif -o reports/security/bandit.sarif

# BEFORE
pip-audit -r reports/security/pip-freeze.txt || echo "::warning::Vulnerabilities found"

# AFTER
pip-audit -r reports/security/pip-freeze.txt --require-hashes=false --strict
```

**Acceptance Criteria:**

- [ ] Security scans fail on actual issues
- [ ] Known/accepted issues are documented in exceptions file
- [ ] CI visibility into security state

**Estimated Total:** 6 hours (1.5 days)

---

## 4. Development Plan - Phase 2 (High)

**Timeline:** Sprint 1-2 (Week 2-4)
**Priority:** High severity issues
**Goal:** Code quality, maintainability improvements

### Epic 2.1: Consolidate conftest.py Files

**Objective:** Single source of truth for test fixtures.

| Task   | Issue IDs | Action                                                 | Effort    | Duration | Dependencies |
| ------ | --------- | ------------------------------------------------------ | --------- | -------- | ------------ |
| 2.1.1  | DUP-01    | Audit fixtures in both conftest.py files               | 2 hours   | 0.5 day  | None         |
| 2.1.2  | DUP-01    | Identify unique fixtures in fixtures/conftest.py       | 1 hour    | 0.25 day | 2.1.1        |
| 2.1.3  | DUP-01    | Merge unique fixtures into tests/conftest.py           | 2 hours   | 0.5 day  | 2.1.2        |
| 2.1.4  | DUP-01    | Delete fixtures/conftest.py                            | 0.5 hours | 0.25 day | 2.1.3        |
| 2.1.5  | DUP-01    | Run full test suite to verify no breakage              | 1 hour    | 0.5 day  | 2.1.4        |

**Acceptance Criteria:**

- [ ] Single conftest.py file
- [ ] All tests pass
- [ ] No duplicate fixture definitions

**Estimated Total:** 6.5 hours (2 days)

---

### Epic 2.2: Re-enable Critical MyPy Error Codes

**Objective:** Restore meaningful type checking by fixing type issues and re-enabling codes.

| Task   | Issue IDs | Error Code     | Action                                           | Effort    | Duration | Dependencies |
| ------ | --------- | -------------- | ------------------------------------------------ | --------- | -------- | ------------ |
| 2.2.1  | PC-004    | `arg-type`     | Run MyPy with `arg-type` enabled, capture errors | 1 hour    | 0.25 day | None         |
| 2.2.2  | PC-004    | `arg-type`     | Fix `arg-type` errors in codebase                | 8 hours   | 2 days   | 2.2.1        |
| 2.2.3  | PC-004    | `arg-type`     | Enable `arg-type` in pre-commit config           | 0.5 hours | 0.25 day | 2.2.2        |
| 2.2.4  | PC-004    | `return-value` | Run MyPy with `return-value` enabled             | 1 hour    | 0.25 day | 2.2.3        |
| 2.2.5  | PC-004    | `return-value` | Fix `return-value` errors in codebase            | 6 hours   | 1.5 days | 2.2.4        |
| 2.2.6  | PC-004    | `return-value` | Enable `return-value` in pre-commit config       | 0.5 hours | 0.25 day | 2.2.5        |
| 2.2.7  | PC-004    | `assignment`   | Run MyPy with `assignment` enabled               | 1 hour    | 0.25 day | 2.2.6        |
| 2.2.8  | PC-004    | `assignment`   | Fix `assignment` errors in codebase              | 4 hours   | 1 day    | 2.2.7        |
| 2.2.9  | PC-004    | `assignment`   | Enable `assignment` in pre-commit config         | 0.5 hours | 0.25 day | 2.2.8        |

**Phased Approach:**

1. Remove ONE error code at a time
2. Run mypy and fix all errors
3. Commit fixes
4. Repeat for next error code

**Example Fix Workflow:**

```bash
# Step 1: Remove arg-type from disabled list
sed -i '/--disable-error-code=arg-type/d' .pre-commit-config.yaml

# Step 2: Run mypy to find issues
mypy src/ --ignore-missing-imports

# Step 3: Fix each error in source files
# ... make code changes ...

# Step 4: Verify no errors
mypy src/ --ignore-missing-imports && echo "Clean!"
```

**Acceptance Criteria:**

- [ ] Three critical MyPy codes re-enabled: `arg-type`, `return-value`, `assignment`
- [ ] No MyPy errors in pre-commit
- [ ] CI passes with new config

**Estimated Total:** 22.5 hours (6 days)

---

### Epic 2.3: Enable Linting on Test Files

**Objective:** Apply code quality standards to test code.

| Task   | Issue IDs       | Action                                                          | Effort    | Duration | Dependencies |
| ------ | --------------- | --------------------------------------------------------------- | --------- | -------- | ------------ |
| 2.3.1  | PC-001          | Create relaxed flake8 config for tests                          | 2 hours   | 0.5 day  | None         |
| 2.3.2  | PC-001          | Run flake8 on tests with relaxed config, capture issues         | 1 hour    | 0.25 day | 2.3.1        |
| 2.3.3  | PC-001          | Fix critical flake8 issues in tests (E722, B008)                | 4 hours   | 1 day    | 2.3.2        |
| 2.3.4  | PC-001          | Remove test exclusion from flake8 pre-commit                    | 0.5 hours | 0.25 day | 2.3.3        |
| 2.3.5  | PC-002          | Create relaxed mypy config for tests                            | 2 hours   | 0.5 day  | None         |
| 2.3.6  | PC-002          | Remove test exclusion from mypy pre-commit                      | 0.5 hours | 0.25 day | 2.3.5        |

**Recommended Test-Specific Relaxations:**

```yaml
# Add to .pre-commit-config.yaml for tests only
# Consider a separate flake8 config for tests
--per-file-ignores=src/tests/*:S101,S311  # Allow assert and random in tests
```

**Acceptance Criteria:**

- [ ] Tests pass flake8 with relaxed config
- [ ] Tests pass mypy with relaxed config
- [ ] Pre-commit hooks apply to test files

**Estimated Total:** 10 hours (3 days)

---

## 5. Development Plan - Phase 3 (Medium)

**Timeline:** Sprint 2-3 (Week 4-6)
**Priority:** Medium severity issues
**Goal:** Improve test reliability and coverage quality

### Epic 3.1: Fix Logically Weak Tests

**Objective:** Strengthen test assertions to catch real issues.

| Task   | Issue IDs       | Action                                                 | Effort  | Duration | Dependencies |
| ------ | --------------- | ------------------------------------------------------ | ------- | -------- | ------------ |
| 3.1.1  | LW-001, LW-002  | Identify tests with `in [200, 503]` pattern            | 1 hour  | 0.25 day | None         |
| 3.1.2  | LW-001, LW-002  | Analyze expected behavior for each endpoint            | 2 hours | 0.5 day  | 3.1.1        |
| 3.1.3  | LW-001, LW-002  | Tighten assertions to specific expected codes          | 4 hours | 1 day    | 3.1.2        |
| 3.1.4  | LW-004          | Add assertions to test_candidate_visibility.py         | 2 hours | 0.5 day  | None         |
| 3.1.5  | LW-003          | Remove or implement placeholder tests                  | 2 hours | 0.5 day  | None         |

**Example Fix:**

```python
# BEFORE (Accepts any status)
def test_set_params_with_learning_rate(self, app_client):
    response = app_client.post("/api/set_params", json={"learning_rate": 0.01})
    assert response.status_code in [200, 400, 500]

# AFTER (Expects specific status)
def test_set_params_with_learning_rate(self, app_client):
    response = app_client.post("/api/set_params", json={"learning_rate": 0.01})
    assert response.status_code == 200  # Or 400 if validation expected
```

**Acceptance Criteria:**

- [ ] No tests accept 500-level errors as success
- [ ] All tests have meaningful assertions
- [ ] Placeholder tests removed or implemented

**Estimated Total:** 11 hours (3 days)

---

### Epic 3.2: Address Unconditional Skips

**Objective:** Either fix skipped tests or document why they must remain skipped.

| Task  | Issue IDs                | Action                                                    | Effort  | Duration | Dependencies |
| ----- | ------------------------ | --------------------------------------------------------- | ------- | -------- | ------------ |
| 3.2.1 | SK-005, SK-006, SK-007   | Analyze WebSocket test async compatibility                | 4 hours | 1 day    | None         |
| 3.2.2 | SK-005, SK-006, SK-007   | Implement async-compatible WebSocket tests or move to e2e | 8 hours | 2 days   | 3.2.1        |
| 3.2.3 | SK-001 to SK-004, SK-008 | Document remaining valid skips with ADR                   | 2 hours | 0.5 day  | None         |

**Example Implementation:**

```python
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_training_websocket_receives_state_messages():
    """Test WebSocket state message broadcast."""
    import asyncio
    from httpx_ws import aconnect_ws

    async with aconnect_ws("ws://localhost:8050/ws/training") as ws:
        # Trigger state change
        # ...

        # Wait for message with timeout
        message = await asyncio.wait_for(ws.receive_json(), timeout=5.0)

        assert message["type"] == "state"
        assert "status" in message["data"]
```

**Acceptance Criteria:**

- [ ] WebSocket tests either run or are in e2e category
- [ ] All skips have documented justification
- [ ] Skip count reduced where possible

**Estimated Total:** 14 hours (3.5 days)

---

### Epic 3.3: Fix Exception Suppression in Tests

**Objective:** Tests should not silently swallow exceptions.

| Task  | Issue IDs        | Action                                                  | Effort  | Duration | Dependencies |
| ----- | ---------------- | ------------------------------------------------------- | ------- | -------- | ------------ |
| 3.3.1 | EXC-01 to EXC-04 | Identify all `contextlib.suppress` usage in tests       | 1 hour  | 0.25 day | None         |
| 3.3.2 | EXC-01 to EXC-04 | Replace with explicit exception handling and assertions | 4 hours | 1 day    | 3.3.1        |

**Action:** Review each `contextlib.suppress` and replace with:

1. `pytest.raises` if exception is expected
2. Proper assertions if no exception expected
3. Document why suppression is necessary if unavoidable

**Acceptance Criteria:**

- [ ] No `contextlib.suppress(Exception)` in tests
- [ ] Tests explicitly verify expected exceptions

**Estimated Total:** 5 hours (1.25 days)

---

### Epic 3.4: Re-enable Additional Flake8 Checks

**Objective:** Catch more code quality issues.

| Task  | Issue IDs | Error Code | Action                                          | Effort  | Duration | Dependencies |
| ----- | --------- | ---------- | ----------------------------------------------- | ------- | -------- | ------------ |
| 3.4.1 | PC-005    | F401       | Re-enable F401 (unused imports), fix issues     | 4 hours | 1 day    | None         |
| 3.4.2 | PC-005    | E722       | Re-enable E722 (bare except), fix issues        | 4 hours | 1 day    | None         |
| 3.4.3 | PC-005    | B008       | Re-enable B008 (mutable default), fix issues    | 2 hours | 0.5 day  | None         |
| 3.4.4 | PC-005    | B905       | Re-enable B905 (zip without strict), fix issues | 1 hour  | 0.25 day | None         |

**Acceptance Criteria:**

- [ ] F401, E722, B008, B905 enabled
- [ ] No violations in codebase
- [ ] CI passes

**Estimated Total:** 11 hours (2.75 days)

---

### Epic 3.5: Remove Duplicate Test Classes

**Objective:** Eliminate redundant test code.

| Task  | Issue IDs | Action                                                                                                                                   | Effort  | Duration | Dependencies |
| ----- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------- | -------- | ------------ |
| 3.5.1 | DUP-02    | Analyze test_main_coverage_95.py for unique vs duplicate classes                                                                         | 2 hours | 0.5 day  | None         |
| 3.5.2 | DUP-02    | Remove duplicate classes: TestHealthCheckEndpoint, TestStateEndpoint, TestStatusEndpoint, TestRootEndpoint, TestTrainingControlEndpoints | 2 hours | 0.5 day  | 3.5.1        |
| 3.5.3 | DUP-02    | Run coverage comparison to verify no lost coverage                                                                                       | 1 hour  | 0.25 day | 3.5.2        |

**Acceptance Criteria:**

- [ ] No duplicate test class definitions
- [ ] Coverage maintained
- [ ] Tests pass

**Estimated Total:** 5 hours (1.25 days)

---

### Epic 3.6: Fix Tests Documenting Bugs

**Objective:** Convert bug-documenting tests to proper xfail markers.

| Task  | Issue IDs | File                       | Test                   | Action                                            | Effort  | Duration |
| ----- | --------- | -------------------------- | ---------------------- | ------------------------------------------------- | ------- | -------- |
| 3.6.1 | CQ-001    | test_logger_coverage_95.py | `test_verbose_logging` | Either implement VERBOSE level OR mark as `xfail` | 2 hours | 0.5 day  |
| 3.6.2 | CQ-001    | test_logger_coverage_95.py | `test_empty_yaml_file` | Fix underlying bug OR mark as `xfail` with ticket | 2 hours | 0.5 day  |

**Example Fix:**

```python
# BEFORE (Documents bug)
def test_verbose_logging(self):
    with pytest.raises(AttributeError, match="module 'logging' has no attribute 'VERBOSE'"):
        logger.verbose("Test verbose message")

# AFTER (Marks known limitation)
@pytest.mark.xfail(reason="VERBOSE level not implemented - JIRA-123")
def test_verbose_logging(self):
    """Test verbose logging when implemented."""
    logger.verbose("Test verbose message")
    # Will fail until VERBOSE is implemented, then passes
```

**Estimated Total:** 4 hours (1 day)

---

## 6. Development Plan - Phase 4 (Low/Tech Debt)

**Timeline:** Sprint 3+ (Week 6-8)
**Priority:** Low severity and technical debt
**Goal:** Polish and maintain code quality

### Epic 4.1: Configuration Standardization

| Task  | Issue IDs | File           | Action                                            | Effort  | Duration |
| ----- | --------- | -------------- | ------------------------------------------------- | ------- | -------- |
| 4.1.1 | CFG-01    | .coveragerc    | Standardize coverage fail_under to 80% everywhere | 1 hour  | 0.25 day |
| 4.1.2 | CFG-02    | pyproject.toml | Re-enable pytest warnings, address issues         | 4 hours | 1 day    |

**Estimated Total:** 5 hours (1.25 days)

---

### Epic 4.2: Documentation and Remaining Cleanup

| Task  | Issue IDs | Action                            | Effort  | Duration |
| ----- | --------- | --------------------------------- | ------- | -------- |
| 4.2.1 | PC-006    | Enable markdown linting for docs/ | 2 hours | 0.5 day  |
| 4.2.2 | -         | Document test directory structure | 2 hours | 0.5 day  |
| 4.2.3 | CQ-002    | Update misleading test docstrings | 2 hours | 0.5 day  |

**Estimated Total:** 6 hours (1.5 days)

---

### Epic 4.3: Future MyPy Improvements

**Objective:** Re-enable remaining disabled codes incrementally.

| Task  | Issue IDs | Error Code | Action                                         | Effort  | Duration |
| ----- | --------- | ---------- | ---------------------------------------------- | ------- | -------- |
| 4.3.1 | PC-004    | -          | Assess remaining MyPy disabled codes           | 2 hours | 0.5 day  |
| 4.3.2 | PC-004    | `call-arg` | Re-enable call-arg - wrong number/type of args | 4 hours | 1 day    |
| 4.3.3 | PC-004    | `override` | Re-enable override - signature mismatches      | 4 hours | 1 day    |
| 4.3.4 | PC-004    | `no-redef` | Re-enable no-redef - redefinition errors       | 4 hours | 1 day    |
| 4.3.5 | PC-004    | `index`    | Re-enable index - index type errors            | 4 hours | 1 day    |

**Estimated Total:** 18 hours (4.5 days)

---

### Epic 4.4: Address contextlib.suppress Usage (Extended)

**Objective:** Complete review and remediation of exception suppression.

| Task  | Issue IDs | Files                      | Action                                               | Effort  | Duration |
| ----- | --------- | -------------------------- | ---------------------------------------------------- | ------- | -------- |
| 4.4.1 | EXC-04    | test_network_visualizer.py | Review and fix remaining suppress patterns           | 2 hours | 0.5 day  |
| 4.4.2 | EXC-04    | test_decision_boundary.py  | Review and fix remaining suppress patterns           | 2 hours | 0.5 day  |
| 4.4.3 | EXC-04    | All other affected files   | Review and document remaining necessary suppressions | 2 hours | 0.5 day  |

**Estimated Total:** 6 hours (1.5 days)

---

## 7. Effort Summary and Timeline

### 7.1 Effort by Phase

| Phase             | Epics                        | Estimated Hours | Estimated Days |
| ----------------- | ---------------------------- | --------------- | -------------- |
| Phase 1: Critical | 1.1, 1.2, 1.3                | 21 hours        | 5.25 days      |
| Phase 2: High     | 2.1, 2.2, 2.3                | 39 hours        | 11 days        |
| Phase 3: Medium   | 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 | 50 hours        | 12.75 days     |
| Phase 4: Low      | 4.1, 4.2, 4.3, 4.4           | 35 hours        | 8.75 days      |
| **TOTAL**         | **16 Epics**                 | **145 hours**   | **37.75 days** |

### 7.2 Recommended Sprint Allocation

| Sprint   | Focus                                | Epics                        | Target Completion |
| -------- | ------------------------------------ | ---------------------------- | ----------------- |
| Sprint 1 | Critical issues, start high priority | 1.1, 1.2, 1.3, 2.1           | Week 2            |
| Sprint 2 | Complete high priority               | 2.2, 2.3                     | Week 4            |
| Sprint 3 | Medium priority                      | 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 | Week 6            |
| Sprint 4 | Low priority, cleanup                | 4.1, 4.2, 4.3, 4.4           | Week 8            |

### 7.3 Resource Requirements

| Role             | Allocation | Sprints    |
| ---------------- | ---------- | ---------- |
| Senior Developer | 80%        | All        |
| QA Engineer      | 40%        | Sprint 1-3 |
| DevOps Engineer  | 20%        | Sprint 1-2 |

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk                                      | Probability | Impact | Mitigation                                       |
| ----------------------------------------- | ----------- | ------ | ------------------------------------------------ |
| MyPy fixes break existing functionality   | Medium      | High   | Comprehensive testing, phased rollout            |
| Moving files breaks import paths          | Low         | Medium | Update all references, test thoroughly           |
| Stricter linting slows development        | Medium      | Low    | Gradual enforcement, clear documentation         |
| Security fixes reveal new vulnerabilities | Medium      | Medium | Address in priority order                        |
| Re-enabling linting surfaces many errors  | High        | Medium | Phase approach; fix incrementally                |
| MyPy code re-enabling breaks CI           | High        | High   | One code at a time; thorough local testing       |
| WebSocket test conversion is complex      | Medium      | Medium | Allocate extra time; use pytest-asyncio examples |

### 8.2 Process Risks

| Risk                                           | Probability | Impact | Mitigation                                       |
| ---------------------------------------------- | ----------- | ------ | ------------------------------------------------ |
| MyPy fixes take longer than estimated          | High        | Medium | Buffer time built into Phase 2                   |
| Integration with Cascor work creates conflicts | Medium      | Medium | Coordinate with integration team                 |
| Unforeseen test failures after changes         | Medium      | Low    | Thorough testing at each epic completion         |
| Scope creep into non-test code                 | Medium      | Medium | Strict scope limits; separate PRs for app fixes  |
| Coverage temporarily drops                     | Medium      | Low    | Acceptable during refactor; track trend          |
| Team unfamiliar with async testing             | Medium      | Medium | Provide examples; pair programming               |

### 8.3 Schedule Risks

| Risk                                           | Probability | Impact | Mitigation                                       |
| ---------------------------------------------- | ----------- | ------ | ------------------------------------------------ |
| MyPy fixes take longer than estimated          | High        | Medium | Buffer time built into Phase 2                   |
| Integration with Cascor work creates conflicts | Medium      | Medium | Coordinate with integration team                 |
| Unforeseen test failures after changes         | Medium      | Low    | Thorough testing at each epic completion         |

---

## 9. Success Metrics

### 9.1 Quality Metrics

| Metric                     | Current | Target                  | Timeline |
| -------------------------- | ------- | ----------------------- | -------- |
| Tests with `assert True`   | 9       | 0                       | Sprint 1 |
| Non-test files in test dir | 5       | 0                       | Sprint 1 |
| Unconditional skips        | 9       | ≤4 (with documentation) | Sprint 3 |
| MyPy disabled error codes  | 15      | ≤10                     | Sprint 2 |
| Flake8 ignored categories  | 15      | ≤10                     | Sprint 3 |

### 9.2 CI/CD Metrics

| Metric                              | Current  | Target   | Timeline |
| ----------------------------------- | -------- | -------- | -------- |
| Security scans with silent failures | 2        | 0        | Sprint 1 |
| Coverage threshold consistency      | 60/80/80 | 80/80/80 | Sprint 4 |
| Pre-commit coverage of tests        | Excluded | Included | Sprint 2 |

---

## 10. Implementation Guidelines

### 10.1 Testing Changes to Test Suite

Before committing test suite changes:

```bash
# 1. Run affected tests locally
cd src
pytest tests/<changed_file>.py -v

# 2. Run full test suite
pytest tests/ -v

# 3. Verify coverage hasn't dropped
pytest tests/ --cov=. --cov-report=term-missing

# 4. Run pre-commit hooks
pre-commit run --all-files
```

### 10.2 Git Workflow

```bash
# Create feature branch for each phase
git checkout -b test-suite-phase-1-critical-fixes

# Commit frequently with clear messages
git commit -m "fix(tests): Replace assert True with actual assertions in test_button_responsiveness.py"

# Push and create PR for review
git push -u origin test-suite-phase-1-critical-fixes
```

### 10.3 PR Review Checklist

For each PR addressing these issues:

- [ ] Issue ID(s) from this plan referenced in PR description
- [ ] All affected tests pass locally
- [ ] Coverage maintained or improved
- [ ] Pre-commit hooks pass
- [ ] No new lint errors introduced
- [ ] Changes documented in CHANGELOG.md

---

## 11. Verification Checklist

### 11.1 Phase 1 Completion Criteria

- [ ] No `assert True` patterns remain in test files (grep verification)
- [ ] All files in `tests/` directory are valid pytest tests
- [ ] Security scans fail appropriately on issues
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Epic 1.1: All `assert True` patterns eliminated
- [ ] Epic 1.2: All non-test files moved to `util/`
- [ ] Epic 1.3: Security scans fail appropriately on issues
- [ ] Pre-commit hooks pass
- [ ] CI pipeline green

### 11.2 Phase 2 Completion Criteria

- [ ] Epic 2.1: Single conftest.py file
- [ ] Epic 2.2: Three MyPy codes re-enabled (`arg-type`, `return-value`, `assignment`)
- [ ] Epic 2.3: Linting enabled on tests
- [ ] Tests are no longer excluded from flake8/mypy
- [ ] All tests pass
- [ ] No regressions from Phase 1
- [ ] CI pipeline green
- [ ] Coverage ≥80%: `pytest tests/ --cov=. --cov-fail-under=80`

### 11.3 Phase 3 Completion Criteria

- [ ] Skipped WebSocket tests converted to e2e or properly conditional
- [ ] No overly permissive status assertions (`[200, 400, 500]`)
- [ ] No duplicate test classes
- [ ] Bug-documenting tests converted to xfail or fixed
- [ ] F401, E722, B008, B905 Flake8 codes re-enabled
- [ ] contextlib.suppress patterns reviewed and minimized
- [ ] All tests pass

### 11.4 Phase 4 Completion Criteria

- [ ] Coverage threshold consistent at 80% across all configs
- [ ] Pytest warnings not suppressed
- [ ] Documentation linting enabled
- [ ] Test docstrings accurately describe what is tested
- [ ] Additional MyPy codes re-enabled as feasible
- [ ] Remaining contextlib.suppress documented if unavoidable

---

## Appendix A: Issue-to-Task Mapping

| Issue ID           | AMP ID | Task ID(s)  | Priority | Status     |
| ------------------ | ------ | ----------- | -------- | ---------- |
| FP-001 to FP-004   | A1-A4  | 1.1.1       | P0       | ✅ Complete |
| FP-005             | A5     | 1.1.2       | P0       | ✅ Complete |
| FP-006             | A6     | 1.1.3       | P0       | ✅ Complete |
| FP-007, FP-008     | A7, A8 | 1.1.4       | P0       | ✅ Complete |
| FP-009             | -      | 1.1.5       | P0       | ✅ Complete |
| NTF-001 to NTF-005 | B1-B5  | 1.2.1-1.2.7 | P0       | ✅ Complete |
| CI-001, CI-002     | G1, G2 | 1.3.1-1.3.4 | P0       | ✅ Complete |
| DUP-01             | D1     | 2.1.1-2.1.5 | P1       | Pending |
| PC-004             | H4     | 2.2.1-2.2.9 | P1       | Pending |
| PC-001, PC-002     | H1, H2 | 2.3.1-2.3.6 | P1       | Pending |
| LW-001 to LW-004   | E1-E4  | 3.1.1-3.1.5 | P2       | Pending |
| SK-001 to SK-009   | C1-C8  | 3.2.1-3.2.3 | P2       | Pending |
| EXC-01 to EXC-04   | F1-F3  | 3.3.1-3.3.2 | P2       | Pending |
| PC-005             | H5     | 3.4.1-3.4.4 | P2       | Pending |
| DUP-02             | D2     | 3.5.1-3.5.3 | P2       | Pending |
| CQ-001             | -      | 3.6.1-3.6.2 | P2       | Pending |
| CFG-01, CFG-02     | I1, I2 | 4.1.1-4.1.2 | P3       | Pending |
| PC-006             | H6     | 4.2.1       | P3       | Pending |
| CQ-002             | -      | 4.2.3       | P3       | Pending |
| PC-004 (cont.)     | H4     | 4.3.1-4.3.5 | P3       | Pending |
| EXC-04 (cont.)     | -      | 4.4.1-4.4.3 | P3       | Pending |

---

## Appendix B: File-by-File Action Items

### Tests to Fix (assert True) - ✅ COMPLETE (2026-02-04)

| File                                                   | Lines            | Action                      | Phase | Status     |
| ------------------------------------------------------ | ---------------- | --------------------------- | ----- | ---------- |
| src/tests/performance/test_button_responsiveness.py    | 90, 97, 104, 111 | Implement real assertions   | 1     | ✅ Complete |
| src/tests/integration/test_button_state.py             | 33               | Implement real assertions   | 1     | ✅ Complete |
| src/tests/unit/frontend/test_metrics_panel_coverage.py | 373              | Implement real assertions   | 1     | ✅ Complete |
| src/tests/unit/test_dashboard_manager.py               | 239              | Fix exception handling test | 1     | ✅ Complete |
| src/tests/unit/test_config_refactoring.py              | 111              | Verify and fix              | 1     | ✅ Complete |
| src/tests/regression/test_candidate_visibility.py      | Entire file      | Add assertions              | 1     | ✅ Complete |

### Files to Relocate - ✅ COMPLETE (2026-02-04)

| Current Location                                | New Location                                  | Phase | Status     |
| ----------------------------------------------- | --------------------------------------------- | ----- | ---------- |
| src/tests/unit/test_yaml.py                     | util/verification/verify_yaml.py              | 1     | ✅ Complete |
| src/tests/unit/test_dashboard_init.py           | util/verification/verify_dashboard_init.py    | 1     | ✅ Complete |
| src/tests/unit/test_and_verify_button_layout.py | util/verification/verify_button_layout.py     | 1     | ✅ Complete |
| src/tests/unit/implementation_script.py         | util/verification/implementation_script.py    | 1     | ✅ Complete |
| src/tests/integration/test_config.py            | util/verification/verify_config_integration.py | 1     | ✅ Complete |

### Configuration Files to Update

| File                    | Section              | Change                                                         | Phase | Status     |
| ----------------------- | -------------------- | -------------------------------------------------------------- | ----- | ---------- |
| ci.yml                  | bandit step          | Remove `\|\| true`                                             | 1     | ✅ Complete |
| ci.yml                  | pip-audit step       | Change warning to failure                                      | 1     | ✅ Complete |
| .bandit.yml             | (new file)           | Added security scan configuration                               | 1     | ✅ Complete |
| .pre-commit-config.yaml | flake8 exclude       | Remove `^src/tests/`                                           | 2     |
| .pre-commit-config.yaml | mypy exclude         | Remove `^src/tests/`                                           | 2     |
| .pre-commit-config.yaml | mypy args            | Remove `--disable-error-code=arg-type,return-value,assignment` | 2     |
| .pre-commit-config.yaml | flake8 ignore        | Remove F401, E722, B008, B905                                  | 3     |
| .coveragerc             | fail_under           | Change 60 to 80                                                | 4     |
| pyproject.toml          | pytest addopts       | Remove `-p no:warnings`                                        | 4     |
| .pre-commit-config.yaml | markdownlint exclude | Remove `docs/` and `notes/`                                    | 4     |

---

## Appendix C: Implementation Checklist Template

### Phase 1 Completion Checklist

- [x] Epic 1.1: All `assert True` patterns eliminated (2026-02-04)
  - [x] test_button_responsiveness.py - 4 tests fixed
  - [x] test_button_state.py - 1 test fixed
  - [x] test_metrics_panel_coverage.py - 1 test fixed
  - [x] test_dashboard_manager.py - 1 test fixed
  - [x] test_config_refactoring.py - 1 test fixed
  - [x] test_candidate_visibility.py - converted to proper pytest with assertions
- [x] Epic 1.2: All non-test files moved to `util/verification/` (2026-02-04)
  - [x] test_yaml.py → util/verification/verify_yaml.py
  - [x] test_dashboard_init.py → util/verification/verify_dashboard_init.py
  - [x] test_and_verify_button_layout.py → util/verification/verify_button_layout.py
  - [x] implementation_script.py → util/verification/implementation_script.py
  - [x] test_config.py → util/verification/verify_config_integration.py
- [x] Epic 1.3: Security scans fail appropriately on issues (2026-02-04)
  - [x] Bandit `|| true` removed (proper exit code handling added)
  - [x] pip-audit warning changed to failure
  - [x] Added .bandit.yml configuration for security exceptions
- [ ] All Phase 1 tests pass
- [ ] Pre-commit hooks pass
- [ ] CI pipeline green

### Phase 2 Completion Checklist

- [ ] Epic 2.1: Single conftest.py file
  - [ ] Fixtures audited
  - [ ] Unique fixtures merged
  - [ ] fixtures/conftest.py deleted
- [ ] Epic 2.2: Three MyPy codes re-enabled
  - [ ] arg-type enabled and errors fixed
  - [ ] return-value enabled and errors fixed
  - [ ] assignment enabled and errors fixed
- [ ] Epic 2.3: Linting enabled on tests
  - [ ] Flake8 exclusion removed
  - [ ] MyPy exclusion removed
  - [ ] Test-specific relaxations added
- [ ] All tests pass
- [ ] No regressions from Phase 1
- [ ] CI pipeline green

### Phase 3 Completion Checklist

- [ ] Epic 3.1: Logically weak tests fixed
- [ ] Epic 3.2: Skipped tests addressed
- [ ] Epic 3.3: Exception suppression fixed
- [ ] Epic 3.4: Additional Flake8 checks enabled
- [ ] Epic 3.5: Duplicate test classes removed
- [ ] Epic 3.6: Bug-documenting tests converted
- [ ] All tests pass
- [ ] Coverage maintained

### Phase 4 Completion Checklist

- [ ] Epic 4.1: Configuration standardized
- [ ] Epic 4.2: Documentation updated
- [ ] Epic 4.3: Future MyPy improvements
- [ ] Epic 4.4: contextlib.suppress usage addressed
- [ ] All tests pass
- [ ] Full verification complete

---

**Document End:**

*This development plan consolidates findings from both Amp and Claude test suite audits. It should be reviewed and approved before implementation begins. Adjust timelines based on team availability and competing priorities.*
