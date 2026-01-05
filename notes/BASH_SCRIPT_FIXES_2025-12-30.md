# Bash Script Infrastructure Fixes - 2025-12-30

## Overview

This document details the comprehensive analysis and fixes applied to the Juniper Canopy bash script infrastructure. The analysis was performed using the Oracle tool and multiple sub-agents to identify and correct errors preventing scripts from running correctly.

## Script Architecture

The Juniper Canopy bash scripts follow a hierarchical configuration sourcing pattern:

```bash
Script (e.g., get_code_stats.bash)
  └── init.conf (minimal environment setup)
        └── common.conf (shared settings, logging)
              ├── logging.conf (logging functions and levels)
              │     ├── logging_functions.conf (logging function definitions)
              │     └── logging_colors.conf (terminal color definitions)
              ├── common_functions.conf (parent validation functions)
              └── [script_name].conf (script-specific config)
                    └── [script_name]_functions.conf (script-specific functions)
```

---

## Errors Identified and Fixed

### 1. Missing Variable Definitions in init.conf

**Problem:** `logging_functions.conf` uses `LOG_EXT`, `LOG_DIR_NAME`, and `LOG_DIR` variables that were never defined, causing the logging fallback path to fail.

**File:** `conf/init.conf`

**Fix:** Added compatible variable aliases after the LOG_FILE definition:

```bash
#####################################################################################################################################################################################################
# Compatible names for logging_functions helpers
#####################################################################################################################################################################################################
export LOG_EXT="${LOGS_EXT}"
export LOG_DIR_NAME="${LOGS_DIR_NAME}"
export LOG_DIR="${LOGS_DIR}"
```

---

### 2. Missing Global Definitions in common.conf

**Problem:** Several critical variables were used but never defined:

- `BASH_EXT` - used in `common_functions.conf` line 88
- `PARENT_INFO_COUNT` - used in `common_functions.conf` line 84
- `ROOT_UTIL_DIR` - used in `common.conf` lines 372-376
- `PROJ_CONF_DIR` - used in `common.conf` line 483

**File:** `conf/common.conf`

**Fix:** Added definitions after line 88:

```bash
export BASH_EXT="bash"
export PARENT_INFO_COUNT=3  # We pass 3 candidates: cmdline, ps args, PARENT_PATH_PARAM
```

And after line 316:

```bash
export ROOT_UTIL_DIR="${UTILITY_DIR}"
export PROJ_CONF_DIR="${CONF_DIR}"
```

---

### 3. Wrong Function Filename Construction in common.conf

**Problem:** Line 115 defined `COMMON_FUNCTIONS_FILENAME` using `${LOGGING_NAME}_${FUNCTIONS_FILE_ROOT}` which evaluated to `logging_functions.conf` instead of `common_functions.conf`.

**File:** `conf/common.conf`

**Fix:** Changed from:

```bash
export COMMON_FUNCTIONS_FILENAME="${LOGGING_NAME}_${FUNCTIONS_FILE_ROOT}.${CONF_EXT}"
```

To:

```bash
export COMMON_FUNCTIONS_FILENAME="${COMMON_FILE_ROOT}_${FUNCTIONS_FILE_ROOT}.${CONF_EXT}"
```

---

### 4. Incorrect is_defined Check in common.conf

**Problem:** The `is_defined` function returns exit status (0/1), but the code was comparing its stdout output against `${TRUE}`. Since the function doesn't echo anything, the comparison always failed.

**File:** `conf/common.conf`

**Fix:** Changed from:

```bash
[[ "$(is_defined validate_parent_path)" == "${TRUE}" ]] && echo "validate_parent_path is defined: ${?}" || log_fatal "validate_parent_path is not defined. Unable to Continue."
```

To:

```bash
if is_defined validate_parent_path; then
    log_debug "validate_parent_path is defined"
else
    log_fatal "validate_parent_path is not defined. Unable to Continue."
fi
```

---

### 5. Color Definitions Before Colors Sourced in logging.conf

**Problem:** The `COLOR_TRACE`, `COLOR_VERBOSE`, etc., and `LOG_COLORS` array were defined on lines 147-158, but they referenced variables like `BLACK_BOLD_DARK` that weren't defined until `logging_colors.conf` was sourced on line 225. This meant all colors were empty.

**File:** `conf/logging.conf`

**Fix:** Moved the color-related definitions to AFTER `logging_colors.conf` is sourced (after line 227).

---

### 6. Function Config File Naming Mismatch

**Problem:** `get_code_stats.conf` line 81 defined `FUNCTION_CONF_INFIX="_fn"` but the actual functions file was named `get_code_stats_functions.conf` (with `_functions` suffix). This caused the source to fail.

**File:** `conf/get_code_stats.conf`

**Fix:** Changed from:

```bash
export FUNCTION_CONF_INFIX="_fn"
```

To:

```bash
export FUNCTION_CONF_INFIX="_functions"
```

---

### 7. Incorrect grep Argument Ordering

**Problem:** In `get_code_stats.bash` line 152, the grep command had incorrect argument ordering. `FIND_METHOD_PARAMS` contained `"-E --"` which when quoted became a single argument that grep interpreted incorrectly.

**File:** `util/get_code_stats.bash`

**Fix:** Changed from:

```bash
CURRENT_METHODS=$(grep -c "${FIND_METHOD_PARAMS}" "${FIND_METHOD_REGEX}" "${FILE_PATH}")
```

To:

```bash
CURRENT_METHODS=$(grep ${FIND_METHOD_PARAMS} -- "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null || echo "0")
```

---

### 8. Exit Code 2 Instead of Success

**Problem:** `get_code_stats.bash` line 267 exited with code 2, which indicates error to callers.

**File:** `util/get_code_stats.bash`

**Fix:** Changed from:

```bash
exit 2  # TODO: Why is this returning a non-zero value?
```

To:

```bash
exit 0  # Exit successfully
```

---

### 9. Broken round_size and current_size Functions

**Problem:** In `get_code_stats_functions.conf`:

- `round_size()` used undefined variable `DIG`
- `current_size()` incorrectly extracted the numeric part using `${CURRENT_SIZE: -1}` (only gets last character, not the number)

**File:** `conf/get_code_stats_functions.conf`

**Fix:** Rewrote both functions:

```bash
function round_size() {
    SIZEF="${1}"
    SIZE="${SIZEF%.*}"
    FRAC="${SIZEF#*.}"
    if [[ "${FRAC}" == "${SIZEF}" ]]; then
        FRAC="0"
    fi
    DEC="0.${FRAC}"
    if (( $(echo "${DEC} >= 0.5" | bc -l) )); then
        SIZE=$(( SIZE + 1 ))
    fi
    echo "${SIZE}"
}

function current_size() {
    CURRENT_SIZE="${1}"
    LABEL="${CURRENT_SIZE: -1}"
    SIZEF="${CURRENT_SIZE%?}"  # Strip last character to get numeric part
    # ... rest of function
}
```

---

### 10. Boolean Inversion in get_module_filenames.conf

**Problem:** Lines 40-41 defined `TRUE="1"` and `FALSE="0"` which is INVERTED from the convention used everywhere else (`TRUE="0"`, `FALSE="1"`).

**File:** `conf/get_module_filenames.conf`

**Fix:** Changed to match standard convention:

```bash
export TRUE="0"
export FALSE="1"
```

---

### 11. Relative Path Issues for init.conf

**Problem:** All util scripts used relative paths like `"../conf/init.conf"` which failed when run from different directories.

**Files:**

- `util/get_code_stats.bash`
- `util/get_module_filenames.bash`
- `util/get_file_todo.bash`

**Fix:** Changed to use script-relative paths:

```bash
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"
export PARENT_PATH_PARAM="${SCRIPT_PATH}"
INIT_CONF="$(realpath "${SCRIPT_DIR}/../conf/init.conf")"
```

---

### 12. Invalid return at Top Level

**Problem:** `get_module_filenames.bash` and `get_file_todo.bash` used `return` at the top level of the script, which is only valid in functions or sourced files.

**Files:**

- `util/get_module_filenames.bash`
- `util/get_file_todo.bash`

**Fix:** Changed to:

```bash
exit 0
```

---

### 13. Missing usage() Functions

**Problem:** Multiple scripts called `usage()` function that was never defined.

**Files:**

- `util/get_module_filenames.bash`
- `util/get_file_todo.bash`

**Fix:** Added `usage()` function definitions to each script.

---

### 14. Hardcoded Paths in __git_log_weeks.bash

**Problem:** The script had hardcoded project paths that didn't match the JuniperCanopy structure, pointing to `~/Development/python/Juniper/conf/common.conf` instead of the correct path.

**File:** `util/__git_log_weeks.bash`

**Fix:** Changed to use script-relative path resolution and source init.conf pattern.

---

### 15. HELP_SHORT Typos

**Problem:** Some config files had `HELP_SHOR` instead of `HELP_SHORT`.

**Files:**

- `conf/get_code_stats.conf`
- `conf/get_file_todo.conf`

**Fix:** Corrected the typo to `HELP_SHORT`.

---

### 16. Extra Shifts in Argument Parsing

**Problem:** In `get_file_todo.bash`, the argument parsing did extra shifts after reading parameters, causing issues.

**File:** `util/get_file_todo.bash`

**Fix:** Removed the extra `shift` commands after reading parameter values.

---

### 17. Missing Shift in While Loop

**Problem:** In `get_module_filenames.bash`, the while loop didn't shift after processing each argument, causing infinite loops.

**File:** `util/get_module_filenames.bash`

**Fix:** Added `shift` at the end of the case statement.

---

### 18. Spurious Debug Output

**Problem:** `get_module_filenames.bash` had a debug line that output to stdout.

**File:** `util/get_module_filenames.bash`

**Fix:** Removed the line:

```bash
echo "get_module_filenames.bash -26"
```

---

### 19. Logging to stdout Interfering with Script Output

**Problem:** Trace-level logging was going to stdout via `tee`, polluting script output that other scripts depended on.

**File:** `conf/logging.conf`

**Fix:** Changed default log level from TRACE to WARNING:

```bash
export DEFAULT_LEVEL="${WARNING_LEVEL}"
```

---

## Remaining Issues

The following issues remain for future work:

1. **ps command output pollution:** The `ps -o args=` command returns too much output on Linux, polluting the parent process detection.

2. **Logging to stdout:** The logging functions output to stdout via `tee`. For scripts that need clean stdout, logging should go to stderr only.

3. **Subshell function availability:** When scripts call other scripts as subprocesses, exported functions are not available, causing "command not found" errors for functions like `evaluate_log_level`.

---

## Verification Commands

To verify syntax of all files:

```bash
cd /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy
for f in conf/*.conf; do bash -n "$f" && echo "$f: OK"; done
for f in util/*.bash; do bash -n "$f" && echo "$f: OK"; done
```

To test get_module_filenames.bash:

```bash
./util/get_module_filenames.bash --full 0 2>&1 | tail -30
```

---

## Files Modified

### Configuration Files

- `conf/init.conf`
- `conf/common.conf`
- `conf/logging.conf`
- `conf/get_code_stats.conf`
- `conf/get_code_stats_functions.conf`
- `conf/get_module_filenames.conf`
- `conf/get_file_todo.conf`

### Script Files

- `util/get_code_stats.bash`
- `util/get_module_filenames.bash`
- `util/get_file_todo.bash`
- `util/__git_log_weeks.bash`

---

## Summary

A total of **19 distinct error categories** were identified and fixed across **11 files**. The primary issues centered around:

1. **Missing variable definitions** - Critical variables undefined
2. **Path resolution** - Relative paths failing from different directories
3. **Boolean inconsistency** - Inverted TRUE/FALSE conventions
4. **Sourcing order** - Dependencies sourced after they were needed
5. **Function naming** - Mismatched filename patterns
6. **Argument parsing** - Incorrect handling of command line arguments
7. **Exit codes** - Scripts returning error codes on success

The infrastructure is now significantly more robust, though some issues related to logging output interacting with script output remain for future refinement.
