# Bash Script Infrastructure Fixes - 2025-12-31

## Overview

This document details the analysis, identification, and correction of errors in the Juniper Canopy bash script infrastructure. The scripts follow an architecture where each script sources an `init.conf` file that sets up the environment, which then sources a `common.conf` file containing shared settings, and finally sources each script's specific config file.

## Script Architecture

```bash
Script (e.g., get_code_stats.bash)
    └── sources: conf/init.conf
            └── sources: conf/common.conf
                    ├── sources: conf/logging.conf
                    │       └── sources: conf/logging_functions.conf
                    │       └── sources: conf/logging_colors.conf
                    ├── sources: conf/common_functions.conf
                    └── sources: conf/<script_name>.conf
                            └── sources: conf/<script_name>_functions.conf (if exists)
```

---

## Errors Identified and Solutions

### 1. Misleading Variable Name in init.conf

**File:** `conf/init.conf`  
**Issue:** The variable `UTIL_DIR` was set to point to the `conf/` directory (the directory containing `init.conf`), not the `util/` directory as the name implies.

**Original Code (lines 68-72):**

```bash
export CURRENT_PATH="$(realpath "${BASH_SOURCE[0]}")"
export UTIL_DIR="$(dirname "${CURRENT_PATH}")"          # Actually conf/, not util/!
export PROJ_DIR="$(dirname "${UTIL_DIR}")"
```

**Solution:** Renamed `UTIL_DIR` to `INIT_CONF_DIR` to accurately reflect that it points to the config directory:

```bash
export CURRENT_PATH="$(realpath "${BASH_SOURCE[0]}")"
export INIT_CONF_DIR="$(dirname "${CURRENT_PATH}")"     # Correctly named
export PROJ_DIR="$(dirname "${INIT_CONF_DIR}")"
```

**Impact:** Prevents confusion and potential bugs in scripts that might incorrectly assume `UTIL_DIR` points to the utilities directory.

---

### 2. Hard-coded Project Paths in get_code_stats.conf

**File:** `conf/get_code_stats.conf`  
**Issue:** The script redefined `PROJ_DIR`, `UTIL_DIR`, and `CONF_DIR` using hard-coded paths based on `$HOME/Development/python/JuniperCanopy/juniper_canopy`. This broke portability and ignored the correctly computed paths from `init.conf`/`common.conf`.

**Original Code (lines 85-99):**

```bash
export HOME_DIR="${HOME}"
export PROJ_NAME="JuniperCanopy"
export APP_NAME="juniper_canopy"
export PROJ_LANG_DIR_NAME="python"
export DEV_DIR_NAME="Development"
export DEV_DIR="${HOME_DIR}/${DEV_DIR_NAME}"
export PROJ_ROOT_DIR="${DEV_DIR}/${PROJ_LANG_DIR_NAME}"
export PROJ_DIR="${PROJ_ROOT_DIR}/${PROJ_NAME}/${APP_NAME}"
export UTIL_DIR_NAME="util"
export UTIL_DIR="${PROJ_DIR}/${UTIL_DIR_NAME}"
export CONF_DIR_NAME="conf"
export CONF_DIR="${PROJ_DIR}/${CONF_DIR_NAME}"
```

**Solution:** Removed hard-coded path computation and reused the paths from `init.conf`/`common.conf`:

```bash
export PROJ_NAME="JuniperCanopy"
# Reuse PROJ_DIR from init.conf/common.conf - do not override
: "${PROJ_DIR:?PROJ_DIR must be set by init.conf/common.conf}"
# Reuse UTIL_DIR from common.conf (ROOT_UTIL_DIR alias)
export UTIL_DIR="${ROOT_UTIL_DIR:-${PROJ_DIR}/util}"
# Reuse CONF_DIR from common.conf (PROJ_CONF_DIR alias)
export CONF_DIR="${PROJ_CONF_DIR:-${PROJ_DIR}/conf}"
```

**Impact:** Scripts now work correctly regardless of where the repository is cloned.

---

### 3. Missing Validation for Function Config File

**File:** `conf/get_code_stats.conf`  
**Issue:** The script attempted to source `get_code_stats_functions.conf` without first validating the file exists. On failure, it only logged an error and continued, leading to undefined function errors later.

**Original Code (lines 104-118):**

```bash
CONF_FUNCTION_FILE="${CONF_DIR}/${CONF_FUNCTION_FILE_NAME}"

if [[ "${DEBUG}" == "${TRUE}" ]]; then
    source "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
else
    source "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
fi
[[ "${SUCCESS}" != "${TRUE}" ]] && log_error "Failed to source..."
```

**Solution:** Added validation before sourcing and changed `log_error` to `log_fatal` to fail fast:

```bash
CONF_FUNCTION_FILE="${CONF_DIR}/${CONF_FUNCTION_FILE_NAME}"

# Validate the function config file exists before attempting to source
[[ -z "${CONF_FUNCTION_FILE}" || ! -f "${CONF_FUNCTION_FILE}" ]] && log_fatal "Function config file not found: ${CONF_FUNCTION_FILE}"

if [[ "${DEBUG}" == "${TRUE}" ]]; then
    source "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
else
    source "${CONF_FUNCTION_FILE}"; SUCCESS="$?"
fi
[[ "${SUCCESS}" != "${TRUE}" ]] && log_fatal "Failed to source..."
```

**Impact:** Early failure with clear error message instead of confusing "command not found" errors later.

---

### 4. Incorrect grep Argument Order for Method Counting

**File:** `util/get_code_stats.bash`  
**Issue:** The `grep` command had arguments in wrong order - the options `-E --` were quoted as strings instead of being passed as options.

**Original Code (line 164):**

```bash
CURRENT_METHODS=$(grep -c "${FIND_METHOD_PARAMS}" "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null || echo "0")
# Where FIND_METHOD_PARAMS="-E --" - but this was treated as a pattern, not options!
```

**Solution:** Passed options directly instead of through a variable:

```bash
CURRENT_METHODS="$(grep -c -E -- "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null | tr -d '[:space:]')"
[[ -z "${CURRENT_METHODS}" ]] && CURRENT_METHODS="0"
```

**Impact:** Method counting now works correctly - went from 0 methods detected to 389 methods.

---

### 5. Incorrect GIT_LOG_SCRIPT_NAME in common.conf

**File:** `conf/common.conf`  
**Issue:** The script name constant `GIT_LOG_SCRIPT_NAME` was set to `git_log_weeks.bash` but the actual file is `__git_log_weeks.bash`.

**Original Code (line 362):**

```bash
export GIT_LOG_SCRIPT_NAME="git_log_weeks.bash"
```

**Solution:** Updated to match the actual filename:

```bash
export GIT_LOG_SCRIPT_NAME="__git_log_weeks.bash"
```

**Impact:** Scripts using this constant now find the correct file.

---

### 6. Unquoted Variable in Logging Validation

**File:** `conf/logging.conf` and `conf/logging_functions.conf`  
**Issue:** Variables in test expressions were not quoted, which could cause syntax errors if the variables were empty.

**Original Code:**

```bash
# logging.conf line 175:
[[ ( ${LOG_FUNCTIONS_FILE} == "" ) || ( ! -f "${LOG_FUNCTIONS_FILE}" ) ]] && log_fatal ...

# logging_functions.conf line 109:
[[ ( ${LOG_FILE} == "" ) || ( ! -f "${LOG_FILE}" ) ]] && return ...
```

**Solution:** Used proper quoting and the `-z` test for empty strings:

```bash
# logging.conf:
[[ -z "${LOG_FUNCTIONS_FILE}" || ! -f "${LOG_FUNCTIONS_FILE}" ]] && log_fatal ...

# logging_functions.conf:
[[ -z "${LOG_FILE}" || ! -f "${LOG_FILE}" ]] && return ...
```

**Impact:** Prevents potential syntax errors with empty variables.

---

### 7. Missing __git_log_weeks.conf File

**File:** `conf/__git_log_weeks.conf` (did not exist)  
**Issue:** The `__git_log_weeks.bash` script sources `init.conf` which leads to `common.conf` trying to source the script's config file at `conf/__git_log_weeks.conf`, which did not exist.

**Solution:** Created the missing config file with the standard structure:

```bash
#!/usr/bin/env bash
# Standard header...

export TRUE="0"
export FALSE="1"
export DEBUG="${FALSE}"

# Guard against double-sourcing
if [[ "${GIT_LOG_WEEKS_CONF_SOURCED}" != "${TRUE}" ]]; then
    GIT_LOG_WEEKS_CONF_SOURCED="${TRUE}"
else
    log_warning "__git_log_weeks.conf already sourced. Skipping re-source."
    [[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
fi

# Basic script configuration (inherits most from common.conf)
# shellcheck disable=SC2155
export SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
# shellcheck disable=SC2155
export SCRIPT_NAME="$(basename "${SCRIPT_PATH}")"
# shellcheck disable=SC2155
export SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"

[[ "${DEBUG}" == "${TRUE}" ]] && exit $(( TRUE )) || return $(( TRUE ))
```

**Impact:** The `__git_log_weeks.bash` script now loads successfully without errors.

---

### 8. Whitespace in grep Output Causing Arithmetic Errors

**File:** `util/get_code_stats.bash`  
**Issue:** The `grep -c` output sometimes contained trailing whitespace or newlines, causing arithmetic comparison errors like `((: 0\n0: syntax error`.

**Original Code:**

```bash
CURRENT_TODOS="$(grep -ic "${SEARCH_TERM_DEFAULT}" "${FILE_PATH}" 2>/dev/null || echo "0")"
CURRENT_METHODS=$(grep -c -E -- "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null || echo "0")
```

**Solution:** Added `tr -d '[:space:]'` to strip all whitespace and proper empty-value handling:

```bash
CURRENT_TODOS="$(grep -ic "${SEARCH_TERM_DEFAULT}" "${FILE_PATH}" 2>/dev/null | tr -d '[:space:]')"
[[ -z "${CURRENT_TODOS}" ]] && CURRENT_TODOS="0"

CURRENT_METHODS="$(grep -c -E -- "${FIND_METHOD_REGEX}" "${FILE_PATH}" 2>/dev/null | tr -d '[:space:]')"
[[ -z "${CURRENT_METHODS}" ]] && CURRENT_METHODS="0"
```

**Impact:** Eliminated all arithmetic syntax errors during script execution.

---

## Test Results

### Before Fixes

- **Files found:** 3 (only searched wrong directory)
- **Methods counted:** 0 (grep arguments wrong)
- **Errors:** Multiple "command not found" and syntax errors
- **Git log:** Failed with "config file not found"

### After Fixes

- **Files found:** 23
- **Methods counted:** 389
- **Lines of code:** 13,468
- **TODOs:** 27
- **Total size:** 556 KB
- **Errors:** None
- **Git log:** Works correctly, shows commits

---

## Files Modified

1. `conf/init.conf` - Renamed UTIL_DIR to INIT_CONF_DIR
2. `conf/common.conf` - Fixed GIT_LOG_SCRIPT_NAME
3. `conf/get_code_stats.conf` - Removed hard-coded paths, added validation
4. `conf/logging.conf` - Fixed variable quoting
5. `conf/logging_functions.conf` - Fixed variable quoting
6. `util/get_code_stats.bash` - Fixed grep options and whitespace handling

## Files Created

1. `conf/__git_log_weeks.conf` - New config file for git log utility script

---

## Recommendations for Future Development

1. **Centralize path resolution:** All path variables should be computed once in `init.conf`/`common.conf` and never overridden in script-specific configs.

2. **Fail fast:** Use `log_fatal` instead of `log_error` for configuration errors that prevent the script from working correctly.

3. **Validate before sourcing:** Always check that a file exists before attempting to source it.

4. **Quote all variables:** Use `"${VAR}"` syntax consistently, especially in test expressions.

5. **Sanitize command output:** When capturing output from commands like `grep -c`, always strip whitespace to ensure clean numeric values.

6. **Test portability:** Test scripts from different working directories and with the repository cloned to different locations.
