# Parent Path Resolution Fix Report

**Date:** 2026-01-02  
**Issue:** Broken parent path resolution when scripts call other scripts  
**Status:** ✅ RESOLVED

## Problem Description

The `get_code_stats.bash` script was failing when it called `__git_log_weeks.bash` because the parent script path was being incorrectly resolved. The configuration system was loading `get_code_stats.conf` instead of `__git_log_weeks.conf`.

### Root Cause Analysis

The issue had three components:

1. **Incorrect PID variable usage**: `common.conf` was using `PPID` (OS parent process ID) instead of `$$` (current shell PID) to identify the calling script. When `__git_log_weeks.bash` was called from `get_code_stats.bash`:
   - `PPID` in `__git_log_weeks.bash` = PID of `get_code_stats.bash`
   - This caused `/proc/${PPID}/cmdline` to return `get_code_stats.bash` instead of `__git_log_weeks.bash`

2. **Incorrect validation order**: The `validate_parent_path` function was checking candidates in order: `PARENT_CMD`, `PARENT_CALL`, `PARENT_PARAM`. Since the PID-based lookups (`PARENT_CMD`, `PARENT_CALL`) resolved to valid files (the wrong ones), the correct `PARENT_PATH_PARAM` was never used.

3. **Unnecessary config sourcing in utility script**: `__get_os_name.bash` was sourcing `common.conf` directly without setting `PARENT_PATH_PARAM`, causing issues when called as a subprocess.

### Log Evidence (Before Fix)

```log
(2026-01-02_13:33:32) common.conf:(525):           PARENT_PID: 2358768
(2026-01-02_13:33:32) common.conf:(529):           PARENT_CMD: bash./util/get_code_stats.bash  ← WRONG!
(2026-01-02_13:33:32) common.conf:(532):           PARENT_CALL: bash ./util/get_code_stats.bash  ← WRONG!
(2026-01-02_13:33:32) common.conf:(534):           PARENT_PARAM: /home/pcalnon/.../util/__git_log_weeks.bash  ← CORRECT but ignored!
```

The `PARENT_PARAM` was correct, but it was validated last and the incorrect PID-based candidates were validated first.

## Solution Implemented

### Fix 1: Introduce CALLING_PID in init.conf

Changed from using `PPID` to `$$` for identifying the calling script:

```bash
# BEFORE (init.conf line 171)
export PARENT_PID="${PPID}"

# AFTER
: "${CALLING_PID:=$$}"     # Current shell PID (the script that sourced init.conf)
export CALLING_PID
: "${PARENT_PID:=${PPID}}" # OS parent PID (preserved for backwards compatibility)
export PARENT_PID
```

### Fix 2: Prioritize PARENT_PATH_PARAM in common.conf

Changed the validation order to check `PARENT_PATH_PARAM` first:

```bash
# BEFORE (common.conf lines 531-542)
validate_parent_path "${PARENT_CMD}" "${PARENT_CALL}" "${PARENT_PARAM}"

# AFTER
validate_parent_path "${PARENT_PARAM}" "${PARENT_CMD}" "${PARENT_CALL}"
```

Also updated PID-based lookups to use `CALLING_PID`:

```bash
export PARENT_CMD="$( tr -d '\0' < /proc/"${CALLING_PID}"/cmdline )"
export PARENT_CALL="$(ps -p "${CALLING_PID}" -o args= 2>/dev/null | head -1)"
```

### Fix 3: Fixed filename prefix in __git_log_weeks.conf

The config was looking for `date_functions.conf` but the actual file is `__date_functions.conf`:

```bash
# BEFORE
export DATE_FUNCTIONS_FILE_PREFIX="${DATE_FUNCTIONS_FILE_NAME_ROOT}${DATE_FUNCTIONS_FILE_NAME_INFIX}"

# AFTER
export DATE_FUNCTIONS_FILE_NAME_PREFIX="__"
export DATE_FUNCTIONS_FILE_PREFIX="${DATE_FUNCTIONS_FILE_NAME_PREFIX}${DATE_FUNCTIONS_FILE_NAME_ROOT}${DATE_FUNCTIONS_FILE_NAME_INFIX}"
```

### Fix 4: Simplified __get_os_name.bash

Removed unnecessary `common.conf` sourcing that was causing loops:

```bash
# BEFORE
source "${ROOT_CONF_FILE}"  # This caused issues!

# AFTER
# NOTE: Do NOT source common.conf here - this script is called as a subprocess
# and sourcing common.conf without PARENT_PATH_PARAM causes issues.
```

## Files Modified

| File | Changes |
|------|---------|
| `conf/init.conf` | Added `CALLING_PID` variable using `$$`, guarded `PARENT_PID` assignment |
| `conf/common.conf` | Changed to use `CALLING_PID` for script resolution, reordered validation priority |
| `conf/__git_log_weeks.conf` | Fixed `__date_functions.conf` filename prefix |
| `util/__get_os_name.bash` | Removed unnecessary `common.conf` sourcing |

## Verification

### Test Result (After Fix)

```log
(2026-01-02_16:27:55) common.conf:(196):  Successfully validated the parent path: "__git_log_weeks.bash" ✅
(2026-01-02_16:27:56) common.conf:(577):  Successfully Validated config file: "__git_log_weeks.conf" ✅
(2026-01-02_16:27:56) common.conf:(604):  Successfully Sourced Parent Script's Primary config file ✅
```

The `get_code_stats.bash` script now runs successfully and correctly sources `__git_log_weeks.conf` when calling `__git_log_weeks.bash`.

## Technical Notes

### Why $$ vs $PPID?

- `$$` - The PID of the current bash process (the script itself)
- `$PPID` - The PID of the parent process (what called the script)

When `get_code_stats.bash` (PID A) calls `__git_log_weeks.bash` (PID B):

- In B's context, `PPID` = A (wrong for identifying B's config)
- In B's context, `$$` = B (correct for identifying B's config)

### Why PARENT_PATH_PARAM First?

The `PARENT_PATH_PARAM` is explicitly set by each calling script before sourcing `init.conf`. It's the most reliable source of truth because:

1. It's set by the script itself
2. It doesn't rely on process/cmdline parsing
3. It handles edge cases like symlinks and relative paths correctly

PID-based methods are fallbacks for backwards compatibility with scripts that don't set `PARENT_PATH_PARAM`.

## Recommendations

1. **Always set PARENT_PATH_PARAM**: Every script that sources `init.conf` should set `PARENT_PATH_PARAM="${SCRIPT_PATH}"` first.

2. **Avoid sourcing common.conf in utility scripts**: Simple utility scripts that are called as subprocesses should not source `common.conf` unless they set `PARENT_PATH_PARAM` properly.

3. **Use function-based architecture**: Instead of subprocess calls like `$(${GET_OS_SCRIPT})`, consider exporting functions and sourcing them once.
