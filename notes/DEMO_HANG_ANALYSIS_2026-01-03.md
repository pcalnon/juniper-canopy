# Demo Script Hang Analysis Report

**Date:** 2026-01-03  
**Issue:** `run_demo.bash` hangs when sourcing `init.conf`  
**Status:** 🔍 ANALYSIS COMPLETE - FIXES PENDING

---

## Executive Summary

The `./demo` launcher (symlink to `util/run_demo.bash` → `util/juniper_canopy-demo.bash`) hangs during initialization due to a **circular dependency** in the shell script configuration chain. When the demo script's primary config file (`conf/juniper_canopy-demo.conf`) is sourced, it spawns `util/__get_project_dir.bash` via command substitution, which in turn sources `conf/common.conf`, creating an infinite recursion loop.

---

## Table of Contents

- [Problem Description](#problem-description)
- [Root Cause Analysis](#root-cause-analysis)
- [Identified Issues](#identified-issues)
- [Fix Design](#fix-design)
- [Development Plan](#development-plan)
- [Testing Plan](#testing-plan)
- [Risk Assessment](#risk-assessment)

---

## Problem Description

### Symptoms

1. Running `./demo` or `./util/run_demo.bash` causes the script to hang indefinitely
2. No error messages are displayed
3. The hang occurs during the configuration sourcing phase (before any application code runs)
4. Other scripts in the project work correctly (those that don't trigger the cycle)

### Reproduction Steps

```bash
cd /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy
./demo
# Script hangs with no output beyond initial shell setup
```

---

## Root Cause Analysis

### The Circular Dependency Chain

The hang is caused by an infinite recursion through the following path:

```bash
1. run_demo.bash (via demo symlink)
   └── sources: conf/init.conf
       └── sources: conf/common.conf
           └── sources: conf/juniper_canopy-demo.conf (PRIMARY_CONF_FILE)
               └── command substitution: $(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")
                   └── spawns: util/__get_project_dir.bash (new process)
                       └── sources: conf/common.conf (line 31)
                           └── sources: conf/juniper_canopy-demo.conf (PRIMARY_CONF_FILE)
                               └── command substitution: $(${GET_PROJECT_SCRIPT}...)
                                   └── spawns: util/__get_project_dir.bash (new process)
                                       └── ... INFINITE LOOP
```

### Key Code Locations

1. **The cycle entry point** - [conf/juniper_canopy-demo.conf:44](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/juniper_canopy-demo.conf#L44):

   ```bash
   export BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")
   ```

2. **The cycle trigger** - [util/__get_project_dir.bash:31](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/util/__get_project_dir.bash#L31):

   ```bash
   source "${ROOT_CONF_FILE}"  # This sources conf/common.conf
   ```

3. **The automatic config sourcing** - [conf/common.conf:486](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/common.conf#L486):

   ```bash
   source "${PRIMARY_CONF_FILE}"; SUCCESS="$?"
   ```

### Why Guards Don't Help

The `COMMON_CONF_SOURCED` guard in `common.conf` does not prevent the cycle because:

- Each `$(${GET_PROJECT_SCRIPT} ...)` starts a **new subprocess**
- Non-exported shell variables like `COMMON_CONF_SOURCED` are not propagated to child processes
- Each subprocess runs `common.conf` fully, detecting the same parent script and sourcing the same config

### Prior Fix Context

A similar issue was fixed on 2026-01-02 for `__get_os_name.bash` (see [FIX_PARENT_PATH_RESOLUTION_2026-01-02.md](FIX_PARENT_PATH_RESOLUTION_2026-01-02.md)). That fix removed the unnecessary `source "${ROOT_CONF_FILE}"` call. However, `__get_project_dir.bash` was **not** included in that fix and still contains the problematic line.

---

## Identified Issues

### Issue 1: Circular Dependency in `__get_project_dir.bash` (CRITICAL)

**File:** [util/__get_project_dir.bash](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/util/__get_project_dir.bash#L31)  
**Severity:** 🔴 Critical (blocks application launch)

**Problem:** The script sources `common.conf` but is called from configs that `common.conf` itself sources, creating infinite recursion.

**Impact:** The demo script hangs indefinitely and cannot be used.

---

### Issue 2: Multiple Config Files Use Vulnerable Pattern (HIGH)

**Affected Files:**

- [conf/juniper_canopy-demo.conf:44](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/juniper_canopy-demo.conf#L44)
- [conf/create_performance_profile.conf:96](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/create_performance_profile.conf#L96)
- [conf/update_weekly.conf:68](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/update_weekly.conf#L68)
- [conf/get_file_todo.conf:177](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/get_file_todo.conf#L177)
- [conf/proto.conf:79](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/conf/proto.conf#L79)

**Severity:** 🟠 High (potential for same hang in other scripts)

**Problem:** These configs all call `$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")` and will cause hangs if `__get_project_dir.bash` sources `common.conf`.

---

### Issue 3: Hardcoded Paths in Utility Scripts (MEDIUM)

**File:** [util/__get_project_dir.bash:20-29](file:///home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/util/__get_project_dir.bash#L20-L29)

**Problem:**

```bash
ROOT_PROJ_NAME="JuniperCanopy"
PROJ_NAME="juniper_canopy"
...
ROOT_PROJ_DIR="${HOME}/${DEV_DIR}/${LANGUAGE_NAME}/${ROOT_PROJ_NAME}/${PROJ_NAME}"
```

**Severity:** 🟡 Medium (reduces portability)

**Impact:** The script only works when the project is located at the exact expected path structure. Other users or different checkout locations will fail.

---

### Issue 4: Side Effects During Config Sourcing (LOW)

**Problem:** Config files perform heavy operations (process spawning, `/proc` filesystem access) during `source` time instead of being purely declarative.

**Severity:** 🟢 Low (architectural concern)

**Impact:** Future changes may accidentally introduce new cycles or hard-to-debug interactions.

---

## Fix Design

### Fix 1: Make `__get_project_dir.bash` Standalone (RECOMMENDED)

**Objective:** Remove the `source "${ROOT_CONF_FILE}"` line and all unused path constants from `__get_project_dir.bash`.

**Rationale:** The script's actual purpose (lines 37-55) is to compute the project directory from an argument path. It does not need any values from `common.conf` to accomplish this.

**New Implementation:**

```bash
#!/usr/bin/env bash
#####################################################################
# Script Name: __get_project_dir.bash
# Description: Returns the absolute path of the project directory
#              given a script or config file path as an argument.
#
# Usage: __get_project_dir.bash <path>
#
# NOTE: This script is intentionally standalone and does NOT source
#       any config files to avoid circular dependency issues.
#####################################################################

set -euo pipefail

# Validate argument
SCRIPT_PATH="${1:-}"
if [[ -z "${SCRIPT_PATH}" ]]; then
    echo "Error: Script path not provided." >&2
    exit 1
fi

# Resolve symlinks
while [[ -L "${SCRIPT_PATH}" ]]; do
    SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"
    SCRIPT_PATH="$(readlink "${SCRIPT_PATH}")"
    if [[ "${SCRIPT_PATH}" != /* ]]; then
        SCRIPT_PATH="${SCRIPT_DIR}/${SCRIPT_PATH}"
    fi
done

# Get absolute paths
SCRIPT_PATH="$(readlink -f "${SCRIPT_PATH}")"
SCRIPT_DIR="$(cd -P "$(dirname -- "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"
PROJECT_DIR="$(dirname -- "${SCRIPT_DIR}")"

echo "${PROJECT_DIR}"
```

**Files to Modify:**

- `util/__get_project_dir.bash` - Replace with standalone version

---

### Fix 2 (Alternative): Use `PROJ_DIR` Directly in Configs

**Objective:** Replace `$(${GET_PROJECT_SCRIPT} ...)` calls in config files with the already-available `PROJ_DIR` variable.

**Rationale:** `PROJ_DIR` is already computed in `init.conf` before any config files are sourced:

```bash
export PROJ_DIR="$(dirname "${INIT_CONF_DIR}")"
```

**Example Change in `juniper_canopy-demo.conf`:**

```bash
# BEFORE:
export BASE_DIR=$(${GET_PROJECT_SCRIPT} "${BASH_SOURCE[0]}")

# AFTER:
export BASE_DIR="${PROJ_DIR}"
```

**Files to Modify:**

- `conf/juniper_canopy-demo.conf`
- `conf/create_performance_profile.conf`
- `conf/update_weekly.conf`
- `conf/get_file_todo.conf`
- `conf/proto.conf`

---

### Fix 3: Apply `__get_os_name.bash` Pattern Consistently

**Objective:** Ensure all helper scripts follow the same pattern established for `__get_os_name.bash`.

**Pattern:**

```bash
# NOTE: Do NOT source common.conf here - this script is called as a subprocess
# and sourcing common.conf without PARENT_PATH_PARAM causes issues.
# This is a simple utility script that only needs to return a single value.
```

---

## Development Plan

### Phase 1: Immediate Fix (Unblock Demo) - Est. 30 min

| Step | Task | Files | Priority |
| ------ | ------ | ------- | ---------- |
| 1.1 | Implement Fix 1: Make `__get_project_dir.bash` standalone | `util/__get_project_dir.bash` | 🔴 Critical |
| 1.2 | Test demo script launches successfully | - | 🔴 Critical |
| 1.3 | Test other util scripts still work | All scripts in `util/` | 🔴 Critical |

### Phase 2: Config Hardening (Optional) - Est. 1 hr

| Step | Task | Files | Priority |
| ------ | ------ | ------- | ---------- |
| 2.1 | Apply Fix 2 to all affected config files | 5 config files | 🟡 Medium |
| 2.2 | Update documentation in affected files | 5 config files | 🟡 Medium |
| 2.3 | Add comments explaining the pattern | All affected files | 🟢 Low |

### Phase 3: Architectural Improvements (Future) - Est. 2-4 hrs

| Step | Task | Files | Priority |
| ------ | ------ | ------- | ---------- |
| 3.1 | Remove hardcoded paths from helper scripts | Multiple util scripts | 🟢 Low |
| 3.2 | Add documentation for shell script architecture | `docs/shell_scripts.md` | 🟢 Low |
| 3.3 | Consider single entry-point init pattern | Architecture redesign | 🟢 Low |

---

## Testing Plan

### Unit Tests for Fix 1

```bash
# Test 1: __get_project_dir.bash returns correct path
$ util/__get_project_dir.bash /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/util/run_demo.bash
# Expected: /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy

# Test 2: __get_project_dir.bash handles missing argument
$ util/__get_project_dir.bash
# Expected: "Error: Script path not provided." and exit code 1

# Test 3: __get_project_dir.bash resolves symlinks
$ util/__get_project_dir.bash /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/demo
# Expected: /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy
```

### Integration Tests

```bash
# Test 4: Demo script launches without hanging
$ timeout 10 ./demo
# Expected: Script starts, displays banner, attempts conda activation

# Test 5: Other util scripts still work
$ ./util/get_code_stats.bash
# Expected: Runs successfully

# Test 6: Nested script calls work
$ bash -c 'export PARENT_PATH_PARAM="$(realpath $0)"; source conf/init.conf; echo "SUCCESS"'
# Expected: Prints "SUCCESS" without hanging
```

### Regression Tests

1. Run existing pytest suite: `cd src && pytest tests/ -v`
2. Verify all shell scripts in `util/` can be sourced
3. Test demo mode in isolation: `cd src && python -c "from demo_mode import DemoMode; print('OK')"`

---

## Risk Assessment

### Fix 1 Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| Other scripts depend on `__get_project_dir.bash` sourcing `common.conf` | Low | Medium | Search codebase for dependencies; none found |
| Hardcoded paths no longer work in certain contexts | Low | Low | The current hardcoded paths aren't used anyway (the argument-based logic is what runs) |
| Symlink resolution differs | Low | Low | Tested with `realpath` and `readlink -f` |

### Fix 2 Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| Configs become non-reusable outside init chain | Medium | Low | Document the assumption; acceptable trade-off |
| `PROJ_DIR` not available in some context | Low | Medium | Only apply to configs that are always sourced via `init.conf` |

---

## Appendix: File Inventory

### Shell Scripts Analyzed

| File | Status | Notes |
| ------ | -------- | ------- |
| `demo` | OK | Symlink to `util/run_demo.bash` |
| `util/run_demo.bash` | OK | Symlink to `util/juniper_canopy-demo.bash` |
| `util/juniper_canopy-demo.bash` | OK | Main demo launcher script |
| `util/__get_project_dir.bash` | 🔴 BUG | Contains circular dependency |
| `util/__get_os_name.bash` | OK | Fixed in prior PR, standalone |
| `util/__git_log_weeks.bash` | OK | Does not trigger cycle |

### Config Files Analyzed

| File | Status | Notes |
| ------ | -------- | ------- |
| `conf/init.conf` | OK | Entry point for initialization |
| `conf/common.conf` | OK | Main config, auto-sources primary configs |
| `conf/common_functions.conf` | OK | Function definitions |
| `conf/logging.conf` | OK | Logging setup |
| `conf/logging_functions.conf` | OK | Logging function definitions |
| `conf/logging_colors.conf` | OK | Color definitions |
| `conf/juniper_canopy-demo.conf` | ⚠️ | Uses vulnerable pattern (fix optional) |
| `conf/create_performance_profile.conf` | ⚠️ | Uses vulnerable pattern |
| `conf/update_weekly.conf` | ⚠️ | Uses vulnerable pattern |
| `conf/get_file_todo.conf` | ⚠️ | Uses vulnerable pattern |
| `conf/proto.conf` | ⚠️ | Uses vulnerable pattern |

---

## Conclusion

The demo script hang is caused by a well-defined circular dependency that can be fixed by making `util/__get_project_dir.bash` standalone (removing its `source common.conf` line). This is a surgical, low-risk fix that follows the pattern already established for `__get_os_name.bash`.

The recommended development approach is:

1. **Immediate:** Apply Fix 1 to unblock the demo (30 minutes)
2. **Short-term:** Apply Fix 2 to harden configs (1 hour)
3. **Long-term:** Consider architectural improvements for maintainability

All fixes should be tested using the testing plan above before deployment.
