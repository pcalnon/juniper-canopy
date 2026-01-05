# Bash Script Error Fixes - 2026-01-01

## Summary

Fixed critical errors in the Juniper Canopy bash script infrastructure that prevented `get_code_stats.bash` from running successfully.

## Original Error

```bash
2026-01-01_11:02:57) logging.conf:(218): source: [FATAL] Logging function: check_log_file not defined. Cannot validate log file: /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy/logs/juniper_canopy.log.
```

## Root Cause Analysis

### Script Source Chain

The scripts follow this source chain:

```bash
get_code_stats.bash
  └── init.conf
        └── common.conf
              ├── logging.conf
              │     └── logging_functions.conf (defines check_log_file, is_defined)
              │     └── logging_colors.conf
              └── common_functions.conf
              └── get_code_stats.conf
                    └── get_code_stats_functions.conf
```

### Issue 1: Inverted Logic in `is_defined` Check (CRITICAL)

**File:** `conf/logging.conf`, line 215

**Problem:** The `is_defined` function returns 0 (TRUE/success) when a function IS defined. The check was using `&&` which caused `log_fatal` to be called when the function WAS defined (the opposite of intended behavior).

**Before:**

```bash
is_defined "check_log_file" && log_fatal "Logging function: check_log_file not defined.  Cannot validate log file: ${LOG_FILE}."
```

**After:**

```bash
# FIX: Logic was inverted - is_defined returns 0 (TRUE) when function IS defined, so we need to negate
! is_defined "check_log_file" && log_fatal "Logging function: check_log_file not defined.  Cannot validate log file: ${LOG_FILE}."
```

**Explanation:**

- `is_defined` uses `declare -F "$1" &> /dev/null` which returns 0 when function exists
- The original code: `is_defined "check_log_file" && log_fatal "..."`
  - Reads as: "If check_log_file IS defined (returns 0), then log_fatal"
  - This is backwards - it should fatal when NOT defined
- The fix adds `!` to negate: "If check_log_file is NOT defined, then log_fatal"

### Issue 2: Relative Path for init.conf (MODERATE)

**File:** `util/get_code_stats.bash`, lines 64-69

**Problem:** The path to `init.conf` was relative to the current working directory (`../conf/init.conf`), not to the script's location. This meant the script only worked when run from the `util/` directory.

**Before:**

```bash
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="../conf/init.conf"
echo "get_code_stats.bash: SCRIPT_PATH: ${SCRIPT_PATH}"
echo "get_code_stats.bash: INIT_CONF: ${INIT_CONF}"
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }
```

**After:**

```bash
# FIX: Use script-based resolution for init.conf path to work from any directory
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"
export PARENT_PATH_PARAM="${SCRIPT_PATH}"
INIT_CONF="$(realpath "${SCRIPT_DIR}/../conf/init.conf")"
echo "get_code_stats.bash: SCRIPT_PATH: ${SCRIPT_PATH}"
echo "get_code_stats.bash: INIT_CONF: ${INIT_CONF}"
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found at ${INIT_CONF}. Unable to Continue."; exit 1; }
```

**Explanation:**

- Now resolves `init.conf` relative to the script's actual location
- Works regardless of which directory the user runs the script from
- Improved error message to show the path that was attempted

## Verification

After applying fixes, `get_code_stats.bash` runs successfully:

```bash
$ ./util/get_code_stats.bash

Display Stats for the JuniperCanopy Project

Filename                        Lines   Methods   TODOs      Size
----------------------------   ------  --------  ------    ------
websocket_manager.py              761        10       1     28 KB
config_manager.py                 492        19       1     20 KB
...
demo_mode.py                      987        30       1     36 KB


Project JuniperCanopy Summary:

Total Files:   23
Total Methods: 389
Total Lines:   13468
Total TODOs:   27
Total Size:    556 KB


Project JuniperCanopy File Summary:

Longest File(s):  (1578 lines) --  metrics_panel.py
Methods File(s):  (65 methods) --  dashboard_manager.py
Largest File(s):  (68 KB)      --  metrics_panel.py, dashboard_manager.py
Roughest File(s): (4 TODOs)    --  cascor_integration.py
```

## Files Modified

1. `conf/logging.conf` - Fixed inverted `is_defined` check
2. `util/get_code_stats.bash` - Fixed relative path resolution

## Potential Future Improvements (Not Implemented)

1. **DEBUG mode behavior**: When `DEBUG="${TRUE}"`, config files are executed with `bash` instead of `source`, which runs them in subprocesses. Functions defined in those configs are not available to the parent shell. Consider always using `source` for config files.

2. **Platform compatibility**: The `/proc/${PARENT_PID}/cmdline` path used in `common.conf` is Linux-specific and won't work on macOS.

3. **Simplify config chain**: The current multi-level config sourcing is complex. Consider consolidating into fewer files with a single initialization entrypoint.

## Related Documentation

- [AGENTS.md](../AGENTS.md) - Contains script architecture documentation
- [docs/TESTING_MANUAL.md](../docs/testing/TESTING_MANUAL.md) - Testing documentation
