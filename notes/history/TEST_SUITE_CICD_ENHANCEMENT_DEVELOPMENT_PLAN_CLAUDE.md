# JuniperCanopy Test Suite & CI/CD Enhancement Development Plan

**Document Version:** 1.0.0
**Created:** 2026-02-03
**Author:** Claude Opus 4.5 (AI Software Engineer)
**Source Audits:** TEST_SUITE_AUDIT_CANOPY_CLAUDE.md, TEST_SUITE_AUDIT_CANOPY_AMP.md
**Status:** Development Plan - Ready for Review

---

## Executive Summary

This development plan consolidates findings from two independent test suite audits (Claude and AMP) and provides a comprehensive, prioritized roadmap for enhancing the JuniperCanopy test suite and CI/CD pipeline effectiveness.

### Consolidated Issue Summary

| Category                   | Critical | High   | Medium | Low     | Total   |
| -------------------------- | -------- | ------ | ------ | ------- | ------- |
| False-Positive Tests       | 1        | 7      | 1      | 0       | **9**   |
| Non-Test Files in Test Dir | 0        | 5      | 0      | 0       | **5**   |
| Skipped/Placeholder Tests  | 0        | 0      | 9      | 0       | **9**   |
| Exception Suppression      | 0        | 0      | 0      | 25+     | **25+** |
| CI/CD Configuration        | 0        | 3      | 5      | 3       | **11**  |
| Coverage Configuration     | 0        | 0      | 1      | 1       | **2**   |
| **TOTAL**                  | **1**    | **15** | **16** | **29+** | **61+** |

### Estimated Total Effort

| Phase     | Description              | Duration       | Sprint(s)     |
| --------- | ------------------------ | -------------- | ------------- |
| Phase 1   | Critical & High Priority | 3-5 days       | Sprint 1      |
| Phase 2   | Medium Priority          | 5-7 days       | Sprint 2      |
| Phase 3   | Low Priority / Tech Debt | 3-5 days       | Sprint 3+     |
| **Total** |                          | **11-17 days** | **3 Sprints** |

---

## Table of Contents

1. [Audit Comparison & Validation](#1-audit-comparison--validation)
2. [Consolidated Issue Catalog](#2-consolidated-issue-catalog)
3. [Development Plan - Phase 1 (Critical/High)](#3-development-plan---phase-1-criticalhigh)
4. [Development Plan - Phase 2 (Medium)](#4-development-plan---phase-2-medium)
5. [Development Plan - Phase 3 (Low/Tech Debt)](#5-development-plan---phase-3-lowtech-debt)
6. [Implementation Guidelines](#6-implementation-guidelines)
7. [Verification Checklist](#7-verification-checklist)
8. [Risk Assessment](#8-risk-assessment)
9. [Appendix: File-by-File Action Items](#appendix-file-by-file-action-items)

---

## 1. Audit Comparison & Validation

### 1.1 Agreement Between Audits

Both audits independently identified these critical issues:

| Issue                       | Claude Finding | AMP Finding | Validation                                                 |
| --------------------------- | -------------- | ----------- | ---------------------------------------------------------- |
| `assert True` tests         | 8 tests        | 8 tests     | **CONFIRMED** - Same tests identified                      |
| MyPy 15+ disabled codes     | ✓              | ✓           | **CONFIRMED** - Verified in `.pre-commit-config.yaml`      |
| Tests excluded from linting | ✓              | ✓           | **CONFIRMED** - flake8, mypy, bandit all exclude tests     |
| Bandit `\|\| true` in CI    | ✓              | ✓           | **CONFIRMED** - Line 412 in ci.yml                         |
| pip-audit warnings only     | ✓              | ✓           | **CONFIRMED** - Line 428 in ci.yml                         |
| Duplicate conftest.py       | ✓              | Partial     | **CONFIRMED** - Both files exist with overlapping fixtures |

### 1.2 Additional Findings by AMP

AMP identified these issues not found in Claude audit:

| Issue                            | Location                                                                               | Validation Status                                            |
| -------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 4 additional non-test files      | test_yaml.py, test_config.py, test_dashboard_init.py, test_and_verify_button_layout.py | **CONFIRMED** - All are manual scripts with print statements |
| Coverage threshold inconsistency | .coveragerc (60%) vs pyproject.toml (80%)                                              | **CONFIRMED** - Values differ                                |
| Tests documenting bugs           | test_logger_coverage_95.py                                                             | **CONFIRMED** - Uses pytest.raises for expected bugs         |
| Pytest warnings suppressed       | pyproject.toml `-p no:warnings`                                                        | **CONFIRMED** - Line 148                                     |
| contextlib.suppress usage        | Multiple test files                                                                    | **CONFIRMED** - Found 25+ instances                          |

### 1.3 Additional Findings by Claude

Claude identified these issues not fully addressed in AMP audit:

| Issue                               | Location                 | Validation Status                                             |
| ----------------------------------- | ------------------------ | ------------------------------------------------------------- |
| Duplicate test classes              | test_main_coverage_95.py | **CONFIRMED** - Duplicates classes from test_main_coverage.py |
| Overly permissive status assertions | Multiple files           | **CONFIRMED** - `assert status in [200, 400, 500]` patterns   |

### 1.4 Validation Methodology

All findings were validated through:

1. Direct file reading to confirm issue existence
2. Grep pattern matching for issue patterns (`assert True`, `contextlib.suppress`, etc.)
3. Configuration file cross-referencing
4. Best practices comparison against pytest, CI/CD, and Python community standards

---

## 2. Consolidated Issue Catalog

### 2.1 False-Positive Tests (Always Pass)

**Impact:** These tests inflate coverage metrics while providing zero verification. Code changes breaking tested functionality would not be detected.

| ID     | File                           | Test/Line                                 | Issue                                | Severity |
| ------ | ------------------------------ | ----------------------------------------- | ------------------------------------ | -------- |
| FP-001 | test_button_responsiveness.py  | `test_rapid_clicking_prevention`:90       | `assert True`                        | CRITICAL |
| FP-002 | test_button_responsiveness.py  | `test_button_disable_during_execution`:97 | `assert True`                        | HIGH     |
| FP-003 | test_button_responsiveness.py  | `test_button_re_enable_after_timeout`:104 | `assert True`                        | HIGH     |
| FP-004 | test_button_responsiveness.py  | `test_button_re_enable_after_success`:111 | `assert True`                        | HIGH     |
| FP-005 | test_button_state.py           | `test_button_click_disables_button`:33    | `assert True`                        | HIGH     |
| FP-006 | test_metrics_panel_coverage.py | `test_add_metrics_with_none`:373          | `assert True`                        | HIGH     |
| FP-007 | test_dashboard_manager.py      | Unknown:239                               | `assert True` in except block        | HIGH     |
| FP-008 | test_config_refactoring.py     | Unknown:111                               | `assert True`                        | HIGH     |
| FP-009 | test_candidate_visibility.py   | Entire file                               | No assertions, only print statements | MEDIUM   |

### 2.2 Non-Test Files in Test Directory

**Impact:** Files contribute to test metrics but provide no automated verification. May confuse pytest collection and inflate test counts.

| ID      | File                             | Issue                                                | Severity |
| ------- | -------------------------------- | ---------------------------------------------------- | -------- |
| NTF-001 | test_yaml.py                     | Manual script with try/except and print statements   | HIGH     |
| NTF-002 | test_config.py                   | Manual script with print statements                  | HIGH     |
| NTF-003 | test_dashboard_init.py           | Manual verification script                           | HIGH     |
| NTF-004 | test_and_verify_button_layout.py | Manual verification with `if __name__ == "__main__"` | HIGH     |
| NTF-005 | implementation_script.py         | Test runner script with global variables             | HIGH     |

### 2.3 Skipped/Placeholder Tests

**Impact:** Tests never execute in CI, providing false sense of coverage.

| ID     | File                          | Test                                                | Skip Reason                  | Validity                     |
| ------ | ----------------------------- | --------------------------------------------------- | ---------------------------- | ---------------------------- |
| SK-001 | test_hdf5_snapshots_api.py    | `test_lists_real_hdf5_files`                        | Global patching complex      | Valid - Technical            |
| SK-002 | test_hdf5_snapshots_api.py    | `test_ignores_non_hdf5_files`                       | Global patching complex      | Valid - Technical            |
| SK-003 | test_main_api_endpoints.py    | `test_cors_headers_present`                         | TestClient bypasses CORS     | Valid - Known limitation     |
| SK-004 | test_main_api_endpoints.py    | `test_cors_allows_all_origins`                      | TestClient bypasses CORS     | Valid - Known limitation     |
| SK-005 | test_demo_endpoints.py        | `test_training_websocket_receives_state_messages`   | Async event loop             | Questionable - Fixable       |
| SK-006 | test_demo_endpoints.py        | `test_training_websocket_receives_metrics_messages` | Async event loop             | Questionable - Fixable       |
| SK-007 | test_demo_endpoints.py        | `test_demo_mode_broadcasts_data`                    | Async event loop             | Questionable - Fixable       |
| SK-008 | test_logger_coverage.py       | `test_verbose_logging`                              | Custom level not implemented | Valid - Feature gap          |
| SK-009 | test_parameter_persistence.py | `test_api_set_params_integration`                   | Requires running server      | Questionable - Should be e2e |

### 2.4 CI/CD Configuration Issues

| ID     | File                    | Issue                                         | Line     | Severity |
| ------ | ----------------------- | --------------------------------------------- | -------- | -------- |
| CI-001 | .pre-commit-config.yaml | MyPy: 15 error codes disabled                 | 148-162  | HIGH     |
| CI-002 | .pre-commit-config.yaml | Tests excluded from flake8                    | 134      | HIGH     |
| CI-003 | .pre-commit-config.yaml | Tests excluded from mypy                      | 164      | HIGH     |
| CI-004 | ci.yml                  | Bandit failures suppressed (`\|\| true`)      | 412      | MEDIUM   |
| CI-005 | ci.yml                  | pip-audit uses warnings only                  | 428      | MEDIUM   |
| CI-006 | ci.yml                  | SARIF upload continue-on-error                | 419      | MEDIUM   |
| CI-007 | .pre-commit-config.yaml | Flake8: 15 error codes ignored                | 126      | MEDIUM   |
| CI-008 | .pre-commit-config.yaml | Tests excluded from bandit                    | 181      | MEDIUM   |
| CI-009 | pyproject.toml          | Pytest warnings suppressed                    | 148      | MEDIUM   |
| CI-010 | Various                 | Coverage threshold inconsistency (60% vs 80%) | Multiple | LOW      |
| CI-011 | .pre-commit-config.yaml | Markdown docs excluded from lint              | 195      | LOW      |

### 2.5 Code Quality Issues in Tests

| ID     | Category                            | Files Affected                                                                       | Instance Count | Severity |
| ------ | ----------------------------------- | ------------------------------------------------------------------------------------ | -------------- | -------- |
| CQ-001 | contextlib.suppress usage           | test_network_visualizer.py, test_decision_boundary.py, test_button_responsiveness.py | 25+            | LOW      |
| CQ-002 | Overly permissive status assertions | test_main_coverage.py, test_main_coverage_95.py                                      | 10+            | MEDIUM   |
| CQ-003 | Tests documenting bugs              | test_logger_coverage_95.py                                                           | 2              | MEDIUM   |
| CQ-004 | Duplicate test classes              | test_main_coverage_95.py                                                             | 5 classes      | MEDIUM   |
| CQ-005 | Misleading test docstrings          | test_max_epochs_parameter.py                                                         | 2              | LOW      |

---

## 3. Development Plan - Phase 1 (Critical/High)

**Timeline:** Sprint 1 (3-5 days)
**Priority:** Critical and High severity issues
**Goal:** Eliminate false-positive tests and major CI/CD gaps

### 3.1 Task: Fix False-Positive Tests

**Estimated Effort:** 1.5-2 days
**Risk:** Low - Changes are isolated to test files
**Dependencies:** None

| Sub-Task | File                           | Action                                                                           | LOE |
| -------- | ------------------------------ | -------------------------------------------------------------------------------- | --- |
| 3.1.1    | test_button_responsiveness.py  | Implement real button behavior tests using Dash test utilities or mock callbacks | 4h  |
| 3.1.2    | test_button_state.py           | Implement actual button state verification                                       | 2h  |
| 3.1.3    | test_metrics_panel_coverage.py | Replace `assert True` with proper metrics validation                             | 1h  |
| 3.1.4    | test_dashboard_manager.py      | Replace exception-block `assert True` with proper error testing                  | 1h  |
| 3.1.5    | test_config_refactoring.py     | Verify and fix `assert True` pattern                                             | 1h  |
| 3.1.6    | test_candidate_visibility.py   | Add `assert` statements for visibility checks                                    | 2h  |

**Implementation Notes:**

- For button tests: Use `pytest-dash` or mock the callback context
- For metrics tests: Verify actual metric values or history length changes
- For visibility tests: Convert print-based checks to assertions

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

### 3.2 Task: Relocate Non-Test Files

**Estimated Effort:** 0.5-1 day
**Risk:** Very Low - File moves only
**Dependencies:** None

| Sub-Task | Source File                                 | Destination                       | Action                   | LOE |
| -------- | ------------------------------------------- | --------------------------------- | ------------------------ | --- |
| 3.2.1    | tests/unit/test_yaml.py                     | util/verify_yaml.py               | Move and rename          | 15m |
| 3.2.2    | tests/unit/test_config.py                   | util/verify_config.py             | Move and rename          | 15m |
| 3.2.3    | tests/unit/test_dashboard_init.py           | util/verify_dashboard.py          | Move and rename          | 15m |
| 3.2.4    | tests/unit/test_and_verify_button_layout.py | util/verify_button_layout.py      | Move and rename          | 15m |
| 3.2.5    | tests/unit/implementation_script.py         | util/implementation_script.py     | Move                     | 15m |
| 3.2.6    | tests/integration/test_config.py            | util/verify_config_integration.py | Move and rename          | 15m |
| 3.2.7    | Various                                     | Update imports/references         | Verify no broken imports | 1h  |

**Commands:**

```bash
# Execute file moves
git mv src/tests/unit/test_yaml.py util/verify_yaml.py
git mv src/tests/unit/test_config.py util/verify_config.py
git mv src/tests/unit/test_dashboard_init.py util/verify_dashboard.py
git mv src/tests/unit/test_and_verify_button_layout.py util/verify_button_layout.py
git mv src/tests/unit/implementation_script.py util/implementation_script.py
git mv src/tests/integration/test_config.py util/verify_config_integration.py
```

### 3.3 Task: Enable Linting for Test Files

**Estimated Effort:** 1-1.5 days
**Risk:** Medium - May surface many existing lint errors
**Dependencies:** Should be done after 3.1 and 3.2

| Sub-Task | File                    | Action                                       | LOE  |
| -------- | ----------------------- | -------------------------------------------- | ---- |
| 3.3.1    | .pre-commit-config.yaml | Remove `exclude: ^src/tests/` from flake8    | 15m  |
| 3.3.2    | .pre-commit-config.yaml | Remove `exclude: ^src/tests/` from mypy      | 15m  |
| 3.3.3    | Various test files      | Fix lint errors surfaced by enabling linting | 4-6h |
| 3.3.4    | .pre-commit-config.yaml | Add test-specific relaxations if needed      | 1h   |

**Recommended Test-Specific Relaxations:**

```yaml
# Add to .pre-commit-config.yaml for tests only
# Consider a separate flake8 config for tests
--per-file-ignores=src/tests/*:S101,S311  # Allow assert and random in tests
```

### 3.4 Task: Re-enable Critical MyPy Error Codes

**Estimated Effort:** 1-2 days
**Risk:** High - May surface many type errors
**Dependencies:** 3.3 should be completed first

| Sub-Task | Error Code     | Impact                       | LOE  |
| -------- | -------------- | ---------------------------- | ---- |
| 3.4.1    | `arg-type`     | Catches wrong argument types | 2-4h |
| 3.4.2    | `return-value` | Catches wrong return types   | 2-4h |
| 3.4.3    | `assignment`   | Catches type mismatches      | 2-4h |

**Phased Approach:**

1. Remove ONE error code at a time
2. Run mypy and fix all errors
3. Commit fixes
4. Repeat for next error code

**Example fix workflow:**

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

### 3.5 Task: Fix CI Security Scan Suppression

**Estimated Effort:** 0.5 day
**Risk:** Low - May fail CI on existing issues
**Dependencies:** None

| Sub-Task | File    | Line | Action                                       | LOE  |
| -------- | ------- | ---- | -------------------------------------------- | ---- |
| 3.5.1    | ci.yml  | 412  | Remove `\|\| true` from bandit command       | 15m  |
| 3.5.2    | ci.yml  | 428  | Change pip-audit warning to proper exit code | 15m  |
| 3.5.3    | Various | N/A  | Fix any bandit/pip-audit issues exposed      | 2-4h |

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

---

## 4. Development Plan - Phase 2 (Medium)

**Timeline:** Sprint 2 (5-7 days)
**Priority:** Medium severity issues
**Goal:** Improve test reliability and coverage quality

### 4.1 Task: Convert Skipped WebSocket Tests to E2E

**Estimated Effort:** 2-3 days
**Risk:** Medium - Requires async testing expertise
**Dependencies:** Phase 1 complete

| Sub-Task | Test                                                | Action                                          | LOE |
| -------- | --------------------------------------------------- | ----------------------------------------------- | --- |
| 4.1.1    | `test_training_websocket_receives_state_messages`   | Implement with proper async event loop handling | 4h  |
| 4.1.2    | `test_training_websocket_receives_metrics_messages` | Implement with proper async event loop handling | 4h  |
| 4.1.3    | `test_demo_mode_broadcasts_data`                    | Implement with proper async event loop handling | 4h  |
| 4.1.4    | `test_api_set_params_integration`                   | Move to e2e tests with server startup fixture   | 4h  |

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

### 4.2 Task: Tighten Permissive Status Assertions

**Estimated Effort:** 1-2 days
**Risk:** Low - May expose actual API bugs
**Dependencies:** None

| Sub-Task | File                           | Pattern                            | Action                    | LOE |
| -------- | ------------------------------ | ---------------------------------- | ------------------------- | --- |
| 4.2.1    | test_main_coverage.py          | `assert status in [200, 400, 500]` | Narrow to expected status | 2h  |
| 4.2.2    | test_main_coverage_95.py       | `assert status in [200, 400, 500]` | Narrow to expected status | 2h  |
| 4.2.3    | test_main_coverage_extended.py | `assert status in [200, 400, 500]` | Narrow to expected status | 2h  |

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

### 4.3 Task: Remove Duplicate Test Classes

**Estimated Effort:** 0.5-1 day
**Risk:** Low - Reduces redundancy
**Dependencies:** None

| Sub-Task | File                     | Duplicate Classes                                                                                              | Action                  | LOE |
| -------- | ------------------------ | -------------------------------------------------------------------------------------------------------------- | ----------------------- | --- |
| 4.3.1    | test_main_coverage_95.py | TestHealthCheckEndpoint, TestStateEndpoint, TestStatusEndpoint, TestRootEndpoint, TestTrainingControlEndpoints | Remove duplicates       | 2h  |
| 4.3.2    | Various                  | Verify no lost coverage                                                                                        | Run coverage comparison | 1h  |

### 4.4 Task: Consolidate Duplicate conftest.py

**Estimated Effort:** 0.5-1 day
**Risk:** Medium - May affect fixture resolution
**Dependencies:** None

| Sub-Task | Action                                                 | LOE |
| -------- | ------------------------------------------------------ | --- |
| 4.4.1    | Identify unique fixtures in tests/fixtures/conftest.py | 1h  |
| 4.4.2    | Merge unique fixtures into tests/conftest.py           | 1h  |
| 4.4.3    | Remove tests/fixtures/conftest.py                      | 15m |
| 4.4.4    | Verify all tests still pass                            | 30m |

### 4.5 Task: Fix Tests Documenting Bugs

**Estimated Effort:** 0.5-1 day
**Risk:** Low - Documents known issues
**Dependencies:** None

| Sub-Task | File                       | Test                   | Action                                            | LOE |
| -------- | -------------------------- | ---------------------- | ------------------------------------------------- | --- |
| 4.5.1    | test_logger_coverage_95.py | `test_verbose_logging` | Either implement VERBOSE level OR mark as `xfail` | 2h  |
| 4.5.2    | test_logger_coverage_95.py | `test_empty_yaml_file` | Fix underlying bug OR mark as `xfail` with ticket | 2h  |

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

### 4.6 Task: Re-enable Flake8 Error Codes

**Estimated Effort:** 1-2 days
**Risk:** Medium - May surface existing issues
**Dependencies:** Phase 1 complete

| Sub-Task | Error Code | Impact                                | LOE  |
| -------- | ---------- | ------------------------------------- | ---- |
| 4.6.1    | F401       | Unused imports - identifies dead code | 2-4h |
| 4.6.2    | E722       | Bare except - security/quality issue  | 2-4h |
| 4.6.3    | B008       | Mutable default argument - common bug | 1-2h |
| 4.6.4    | B905       | Zip without strict - potential bug    | 1-2h |

### 4.7 Task: Standardize Coverage Threshold

**Estimated Effort:** 0.5 day
**Risk:** Very Low
**Dependencies:** None

| Sub-Task | File           | Current Value | Target Value | LOE    |
| -------- | -------------- | ------------- | ------------ | ------ |
| 4.7.1    | .coveragerc    | 60            | 80           | 15m    |
| 4.7.2    | pyproject.toml | 80            | 80           | Verify |
| 4.7.3    | ci.yml         | 80            | 80           | Verify |

---

## 5. Development Plan - Phase 3 (Low/Tech Debt)

**Timeline:** Sprint 3+ (3-5 days)
**Priority:** Low severity and technical debt
**Goal:** Polish and maintain code quality

### 5.1 Task: Address contextlib.suppress Usage

**Estimated Effort:** 2-3 days
**Risk:** Low - May expose test failures
**Dependencies:** Phase 2 complete

**Files Affected:** test_network_visualizer.py, test_decision_boundary.py, test_button_responsiveness.py (25+ instances)

**Action:** Review each `contextlib.suppress` and replace with:

1. `pytest.raises` if exception is expected
2. Proper assertions if no exception expected
3. Document why suppression is necessary if unavoidable

### 5.2 Task: Update Misleading Test Docstrings

**Estimated Effort:** 0.5 day
**Risk:** Very Low
**Dependencies:** None

| Sub-Task | File                         | Issue                                    | Action                                                  | LOE |
| -------- | ---------------------------- | ---------------------------------------- | ------------------------------------------------------- | --- |
| 5.2.1    | test_max_epochs_parameter.py | Docstrings claim constraint verification | Update docstrings OR implement actual constraint checks | 2h  |

### 5.3 Task: Re-enable Pytest Warnings

**Estimated Effort:** 0.5-1 day
**Risk:** Low - May expose deprecation warnings
**Dependencies:** None

| Sub-Task | File           | Action                               | LOE  |
| -------- | -------------- | ------------------------------------ | ---- |
| 5.3.1    | pyproject.toml | Remove `-p no:warnings` from addopts | 15m  |
| 5.3.2    | Various        | Address surfaced warnings            | 2-4h |

### 5.4 Task: Enable Documentation Linting

**Estimated Effort:** 0.5-1 day
**Risk:** Very Low
**Dependencies:** None

| Sub-Task | File                    | Action                                                | LOE  |
| -------- | ----------------------- | ----------------------------------------------------- | ---- |
| 5.4.1    | .pre-commit-config.yaml | Remove `docs/` and `notes/` from markdownlint exclude | 15m  |
| 5.4.2    | Various markdown files  | Fix linting errors                                    | 2-4h |

### 5.5 Task: Re-enable Remaining MyPy Codes

**Estimated Effort:** 2-3 days
**Risk:** Medium
**Dependencies:** Phase 1 complete

Re-enable remaining disabled codes in priority order:

1. `call-arg` - Wrong number/type of arguments
2. `override` - Override signature mismatches
3. `no-redef` - Redefinition errors
4. `index` - Index type errors

---

## 6. Implementation Guidelines

### 6.1 Testing Changes to Test Suite

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

### 6.2 Git Workflow

```bash
# Create feature branch for each phase
git checkout -b test-suite-phase-1-critical-fixes

# Commit frequently with clear messages
git commit -m "fix(tests): Replace assert True with actual assertions in test_button_responsiveness.py"

# Push and create PR for review
git push -u origin test-suite-phase-1-critical-fixes
```

### 6.3 PR Review Checklist

For each PR addressing these issues:

- [ ] Issue ID(s) from this plan referenced in PR description
- [ ] All affected tests pass locally
- [ ] Coverage maintained or improved
- [ ] Pre-commit hooks pass
- [ ] No new lint errors introduced
- [ ] Changes documented in CHANGELOG.md

---

## 7. Verification Checklist

### 7.1 Phase 1 Completion Criteria

- [ ] No `assert True` patterns remain in test files (grep verification)
- [ ] All files in `tests/` directory are valid pytest tests
- [ ] Tests are no longer excluded from flake8/mypy
- [ ] At least `arg-type`, `return-value`, `assignment` MyPy codes re-enabled
- [ ] Bandit and pip-audit properly fail CI on issues
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Coverage ≥80%: `pytest tests/ --cov=. --cov-fail-under=80`

### 7.2 Phase 2 Completion Criteria

- [ ] Skipped WebSocket tests converted to e2e or properly conditional
- [ ] No overly permissive status assertions (`[200, 400, 500]`)
- [ ] No duplicate test classes
- [ ] Single conftest.py file
- [ ] Bug-documenting tests converted to xfail or fixed
- [ ] F401, E722, B008, B905 Flake8 codes re-enabled
- [ ] Coverage threshold consistent at 80% across all configs

### 7.3 Phase 3 Completion Criteria

- [ ] contextlib.suppress patterns reviewed and minimized
- [ ] Test docstrings accurately describe what is tested
- [ ] Pytest warnings not suppressed
- [ ] Documentation linting enabled
- [ ] Additional MyPy codes re-enabled as feasible

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk                                     | Probability | Impact | Mitigation                                       |
| ---------------------------------------- | ----------- | ------ | ------------------------------------------------ |
| Re-enabling linting surfaces many errors | High        | Medium | Phase approach; fix incrementally                |
| MyPy code re-enabling breaks CI          | High        | High   | One code at a time; thorough local testing       |
| Test file relocation breaks imports      | Low         | Low    | Grep for imports before moving                   |
| WebSocket test conversion is complex     | Medium      | Medium | Allocate extra time; use pytest-asyncio examples |

### 8.2 Process Risks

| Risk                               | Probability | Impact | Mitigation                                      |
| ---------------------------------- | ----------- | ------ | ----------------------------------------------- |
| Scope creep into non-test code     | Medium      | Medium | Strict scope limits; separate PRs for app fixes |
| Coverage temporarily drops         | Medium      | Low    | Acceptable during refactor; track trend         |
| Team unfamiliar with async testing | Medium      | Medium | Provide examples; pair programming              |

---

## Appendix: File-by-File Action Items

### Tests to Fix (assert True)

| File                                                   | Lines            | Action                      | Phase |
| ------------------------------------------------------ | ---------------- | --------------------------- | ----- |
| src/tests/performance/test_button_responsiveness.py    | 90, 97, 104, 111 | Implement real assertions   | 1     |
| src/tests/integration/test_button_state.py             | 33               | Implement real assertions   | 1     |
| src/tests/unit/frontend/test_metrics_panel_coverage.py | 373              | Implement real assertions   | 1     |
| src/tests/unit/test_dashboard_manager.py               | 239              | Fix exception handling test | 1     |
| src/tests/unit/test_config_refactoring.py              | 111              | Verify and fix              | 1     |
| src/tests/regression/test_candidate_visibility.py      | Entire file      | Add assertions              | 1     |

### Files to Relocate

| Current Location                                | New Location                      | Phase |
| ----------------------------------------------- | --------------------------------- | ----- |
| src/tests/unit/test_yaml.py                     | util/verify_yaml.py               | 1     |
| src/tests/unit/test_config.py                   | util/verify_config.py             | 1     |
| src/tests/unit/test_dashboard_init.py           | util/verify_dashboard.py          | 1     |
| src/tests/unit/test_and_verify_button_layout.py | util/verify_button_layout.py      | 1     |
| src/tests/unit/implementation_script.py         | util/implementation_script.py     | 1     |
| src/tests/integration/test_config.py            | util/verify_config_integration.py | 1     |

### Configuration Files to Update

| File                    | Section              | Change                                                         | Phase |
| ----------------------- | -------------------- | -------------------------------------------------------------- | ----- |
| .pre-commit-config.yaml | flake8 exclude       | Remove `^src/tests/`                                           | 1     |
| .pre-commit-config.yaml | mypy exclude         | Remove `^src/tests/`                                           | 1     |
| .pre-commit-config.yaml | mypy args            | Remove `--disable-error-code=arg-type,return-value,assignment` | 1     |
| ci.yml                  | bandit step          | Remove `\|\| true`                                             | 1     |
| ci.yml                  | pip-audit step       | Change warning to failure                                      | 1     |
| .pre-commit-config.yaml | flake8 ignore        | Remove F401, E722, B008, B905                                  | 2     |
| .coveragerc             | fail_under           | Change 60 to 80                                                | 2     |
| pyproject.toml          | pytest addopts       | Remove `-p no:warnings`                                        | 3     |
| .pre-commit-config.yaml | markdownlint exclude | Remove `docs/` and `notes/`                                    | 3     |

---

**Document End:**

*This development plan should be reviewed and approved before implementation begins. Adjust timelines based on team availability and competing priorities.*
