# Testing Infrastructure Fix Report

**Date:** 2026-01-05  
**Author:** Amp Agent  
**Status:** Resolved

## Summary

Two testing issues were identified and fixed:

1. Test collection failure when running via `run_all_tests.bash` script
2. Unhandled thread exception warning during manual test execution

## Issue 1: Test Collection Failure in run_all_tests.bash

### Problem Description

When tests were launched using the `./tests` script (symlink to `util/run_all_tests.bash`), pytest collected 0 tests and failed with:

```bash
ERROR: file or directory not found: n
```

### Root Cause

The pytest command in [util/run_all_tests.bash](../util/run_all_tests.bash) (lines 68-75) contained literal `\n` characters in the command string:

```bash
RUN_TESTS_WITH_COV_RPT="pytest -v ./src/tests \n \
    --cov=src \n \
    ...
"
```

When evaluated by `eval`, these `\n` sequences were passed to pytest as literal arguments. The backslash (`\`) caused the `n` to be interpreted as a file argument, resulting in `file or directory not found: n`.

### Solution

Removed all `\n` sequences from the pytest command string, using only line continuation backslashes:

```bash
RUN_TESTS_WITH_COV_RPT="pytest -v ./src/tests \
    --cov=src \
    --cov-report=xml:src/tests/reports/coverage.xml \
    --cov-report=term-missing \
    --cov-report=html:src/tests/reports/coverage \
    --junit-xml=src/tests/reports/junit/results.xml \
    --continue-on-collection-errors \
"
```

### File Changed

- [util/run_all_tests.bash](../util/run_all_tests.bash) - Lines 68-75

## Issue 2: ModuleNotFoundError in Manual Test Execution

### Problem Description: Issue 2

When running tests manually from `src/tests`, a `PytestUnhandledThreadExceptionWarning` was generated for `test_broadcast_metrics_import_error`:

```bash
Exception in thread Thread-269 (_training_loop)
...
ImportError: Module not available
```

### Root Cause: Issue 2

The test in [src/tests/unit/test_demo_mode_comprehensive.py](../src/tests/unit/test_demo_mode_comprehensive.py) was patching `DemoMode._broadcast_metrics` at the method level:

```python
with patch("demo_mode.DemoMode._broadcast_metrics") as mock_broadcast:
    mock_broadcast.side_effect = ImportError("Module not available")
```

This caused the `ImportError` to be raised **before** the method's internal `try/except` block could handle it. Since the method runs in a background thread, the exception propagated up as an unhandled thread exception.

### Solution: Issue 2

Changed the patch target to the lower-level `websocket_manager.broadcast_from_thread` function, which is called **inside** the `_broadcast_metrics` method's `try/except` block:

```python
with patch(
    "communication.websocket_manager.websocket_manager.broadcast_from_thread",
    side_effect=ImportError("Module not available"),
):
    demo.start()
    time.sleep(0.2)
    demo.stop()
```

This ensures the exception is raised at the appropriate level and caught by the existing error handling in `_broadcast_metrics`.

### File Changed: Issue 2

- [src/tests/unit/test_demo_mode_comprehensive.py](../src/tests/unit/test_demo_mode_comprehensive.py) - Lines 174-190

## Verification

After applying both fixes:

```bash
$ ./tests
collected 1702 items
...
1668 passed, 34 skipped in 93.40s
Coverage: 84.07%
```

- All 1702 tests collected successfully
- 1668 tests passed
- 34 tests skipped (expected, require external dependencies)
- No unhandled thread exception warnings
- Test coverage: 84.07% (above 60% threshold)

## Lessons Learned

1. **Bash string handling:** Avoid using `\n` inside bash strings intended for `eval`. Use only line continuation backslashes (`\`) at line ends.

2. **Mock targeting:** When testing error handling in threaded code, patch at the level where the exception should be caught, not at the method boundary. This ensures the production error handling code path is exercised.
