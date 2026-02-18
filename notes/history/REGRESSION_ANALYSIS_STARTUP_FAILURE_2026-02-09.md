# JuniperCanopy Startup Regression Analysis

**Project**: JuniperCanopy - Monitoring and Diagnostic Frontend for CasCor NN
**Type**: Regression Analysis & Fix Plan
**Version**: 1.0.0
**Author**: AI Agent
**Created**: 2026-02-09
**Status**: Analysis Complete - Fixes Designed
**Last Updated**: 2026-02-09

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Errors Investigated](#errors-investigated)
- [Analysis Performed](#analysis-performed)
- [Root Causes Identified](#root-causes-identified)
- [Fixes Designed](#fixes-designed)
- [Alternative Approaches Evaluated](#alternative-approaches-evaluated)
- [Additional Tests Needed](#additional-tests-needed)
- [Implementation Priority](#implementation-priority)
- [References](#references)

---

## Executive Summary

The JuniperCanopy application fails on startup when launched via `./try` or `./demo` scripts after the JuniperData integration refactor (commits `a1e89f8` through `33987d2`).
The regression has **three root causes** and **one minor issue**. The primary failure is that `DemoMode.__init__()` now requires a running JuniperData service (by design per CAN-INT-002), but the startup scripts do not ensure the service is available.
The recommended fix is a hybrid approach: auto-launch JuniperData from the startup scripts combined with fail-fast validation in `main.py` and proper `${VAR:default}` config expansion support.

---

## Errors Investigated

### Primary Error: `JuniperDataConfigurationError` on Startup

```bash
File "src/demo_mode.py", line 382, in _generate_spiral_dataset
    raise JuniperDataConfigurationError("JUNIPER_DATA_URL environment variable is required...")
juniper_data_client.exceptions.JuniperDataConfigurationError: JUNIPER_DATA_URL environment variable is required.
    All datasets must be fetched from the JuniperData service.
    Set JUNIPER_DATA_URL=http://localhost:8100 to connect to a local instance.

ERROR:    Application startup failed. Exiting.
```

**Location**: `src/demo_mode.py:382` → called from `DemoMode.__init__():195` → called from `get_demo_mode():1065` → called from `lifespan():127` in `main.py`

### Secondary Error: Environment Override Collisions (6+ warnings)

```bash
Environment override collision at main.file: replacing str with dict
Environment override collision at source.dir: replacing str with dict
```

**Location**: `src/config_manager.py:153` in `_apply_environment_overrides()`

### Secondary Error: Backend Path Contains Trailing `}`

```bash
CasCor backend not found at: .../juniper_canopy/JuniperCascor/juniper_cascor}
```

**Location**: `src/backend/cascor_integration.py:202` via `_resolve_backend_path()`

### Tertiary Error: Orphan Process Kill Failure

```bash
./try: line 114: kill: (353959) - No such process
```

**Location**: `try` script line 114 — attempts to kill CasCor PID that was never launched (because main mode execution path failed before reaching the CasCor launch).

---

## Analysis Performed

### 1. Startup Flow Trace for `./try` Script

Traced the complete execution path:

1. `./try` sources `conf/init.conf` → `conf/common.conf` → `conf/juniper_canopy.conf`
2. `juniper_canopy.conf` exports shell constants including:
   - `DEMO_MODE="${FALSE}"` where `FALSE="1"` (bash convention: 0=true, 1=false)
   - `CASCOR_MAIN_FILE`, `CASCOR_SOURCE_DIR`, `CASCOR_CONFIG_DIR` (all `CASCOR_`-prefixed)
3. `try` script line 85: `if [[ "${DEMO_MODE}" == "${TRUE}" ]]` → FALSE (DEMO_MODE="1", TRUE="0")
4. Takes ELSE branch (main mode, lines 89-114)
5. Python `main.py` loads:
   - Line 196: `force_demo_mode = os.getenv("CASCOR_DEMO_MODE", "0") in ("1", "true",...)` → **False** (env var not set by `try` script)
   - Lines 204-217: `CascorIntegration(backend_path)` raises `FileNotFoundError` → falls back to `demo_mode_active = True`
   - Line 127 (lifespan): `get_demo_mode(update_interval=1.0)` → `DemoMode.__init__()`
   - Line 195 (`DemoMode.__init__`): `self.dataset = self._generate_spiral_dataset(n_samples=200)`
   - Line 380-382: `os.environ.get("JUNIPER_DATA_URL")` returns `None` → raises `JuniperDataConfigurationError`

### 2. Startup Flow Trace for `./demo` Script

1. `./demo` sources `conf/init.conf` → `conf/common.conf` → `conf/juniper_canopy.conf`
2. Line 141: `export CASCOR_DEMO_MODE="${FALSE}"` where `FALSE="0"` in the demo script's init.conf context (TRUE="0", FALSE="1")
   - **Bug**: The bash convention TRUE="0"/FALSE="1" means `${FALSE}` is `"1"`. Python checks for `"1"` which would actually match. However, the variable name is confusing (exporting "FALSE" to mean "enable demo mode").
   - **Regardless**: Neither `./demo` nor `./try` sets `JUNIPER_DATA_URL` → same crash
3. **Neither path sets `JUNIPER_DATA_URL`** → same crash in `DemoMode.__init__()`

### 3. Git History Analysis

The regression was introduced across commits:

| Commit    | Description                                                       | Impact                                         |
| --------- | ----------------------------------------------------------------- | ---------------------------------------------- |
| `a1e89f8` | feat: Integrate JuniperData service for spiral dataset generation | Added JuniperData client, kept local fallback  |
| `4d49322` | fix: update JuniperData API contract                              | Updated parameter handling                     |
| `19cf320` | feat: enhance dataset generation for backward compat              | Added algorithm parameter                      |
| `33987d2` | **Enhance JuniperData integration with error handling**           | **REMOVED local fallback, made URL mandatory** |
| `1bd1396` | Add unit tests for JuniperData integration                        | Tests mock the client (work), runtime doesn't  |

The key breaking change is in `33987d2` which replaced the fallback pattern:

```python
# BEFORE (worked without JuniperData)
juniper_data_url = os.environ.get("JUNIPER_DATA_URL")
if juniper_data_url:
    dataset = self._generate_spiral_dataset_from_juniper_data(...)
    if dataset is not None:
        return dataset
    self.logger.warning("JuniperData unavailable, falling back")
return self._generate_spiral_dataset_local(n_samples)

# AFTER (crashes without JuniperData)
juniper_data_url = os.environ.get("JUNIPER_DATA_URL")
if not juniper_data_url:
    raise JuniperDataConfigurationError("JUNIPER_DATA_URL is required...")
return self._generate_spiral_dataset_from_juniper_data(...)
```

This is **by design** per the integration plan (CAN-INT-002): all datasets must come from JuniperData. The regression is that the **infrastructure** (scripts, service management) was not updated to match the new requirement.

### 4. Config Expansion Bug Analysis

`conf/app_config.yaml` line 272:

```yaml
url: "${JUNIPER_DATA_URL:http://localhost:8100}"
```

`config_manager.py` line 122 uses `os.path.expandvars()` which does NOT support the `${VAR:default}` syntax. When `JUNIPER_DATA_URL` is unset:

- Expected: `http://localhost:8100`
- Actual: `${JUNIPER_DATA_URL:http://localhost:8100}` (literal unexpanded string)

Verified with:

```python
>>> import os
>>> os.path.expandvars("${NONEXIST:default_val}")
'${NONEXIST:default_val}'  # NOT expanded — returned as literal
```

Same bug affects `backend_path: "${CASCOR_BACKEND_PATH:../../JuniperCascor/juniper_cascor}"`:

- When `CASCOR_BACKEND_PATH` is unset, the literal string (including trailing `}`) is passed through
- This explains the trailing `}` in the error: `...juniper_cascor}`

### 5. Environment Override Collision Analysis

`juniper_canopy.conf` exports `CASCOR_MAIN_FILE` and `CASCOR_SOURCE_DIR` as shell environment variables. `config_manager.py:_apply_environment_overrides()` iterates ALL `CASCOR_*` env vars and splits on `_` to create config paths:

- `CASCOR_MAIN_FILE` → `key_path = ['main', 'file']` → tries to set `config['main']['file']`
- `CASCOR_SOURCE_DIR` → `key_path = ['source', 'dir']` → tries to set `config['source']['dir']`

When the YAML config has `main` or `source` as non-dict values (or doesn't have them at all), the code creates/overwrites them with dicts, triggering the collision warning. This happens **every time ConfigManager is instantiated** (multiple times during startup), causing the 6+ warnings.

### 6. Test vs Runtime Gap

The test suite works because `conftest.py` line 26 sets:

```python
os.environ["JUNIPER_DATA_URL"] = "http://localhost:8100"
```

And the session-scoped `mock_juniper_data_client` fixture (line 118) mocks the client. Runtime has no such setup.

---

## Root Causes Identified

### RC-1 (PRIMARY): Missing JuniperData Service Lifecycle Management

**Severity**: CRITICAL — Application cannot start

The JuniperData integration refactor made `JUNIPER_DATA_URL` mandatory and removed all local fallback paths, but:

1. Neither `./try` nor `./demo` scripts export `JUNIPER_DATA_URL`
2. Neither script checks if JuniperData service is running
3. Neither script starts the JuniperData service
4. `main.py` lifespan has no pre-flight validation for JuniperData availability before initializing DemoMode

### RC-2 (SECONDARY): `${VAR:default}` Syntax Not Supported by Config Expansion

**Severity**: HIGH — Config defaults are silently broken

`config_manager.py:_expand_env_vars()` uses `os.path.expandvars()` which only supports `$VAR` and `${VAR}` syntax, NOT `${VAR:default_value}`. All `app_config.yaml` entries using `${VAR:default}` syntax produce literal unexpanded strings when the env var is unset.

Affected config entries:

- `backend.cascor_integration.backend_path: "${CASCOR_BACKEND_PATH:../../JuniperCascor/juniper_cascor}"` → trailing `}` in path
- `backend.juniper_data.url: "${JUNIPER_DATA_URL:http://localhost:8100}"` → URL not resolved
- `security.authentication.secret_key: "${JWT_SECRET_KEY}"` → this one works (no default syntax)

### RC-3 (SECONDARY): Shell-to-Python Environment Variable Namespace Collision

**Severity**: MEDIUM — Noisy warnings, potential config corruption

The bash config (`juniper_canopy.conf`) exports `CASCOR_*`-prefixed env vars for shell scripting purposes (e.g., `CASCOR_MAIN_FILE`, `CASCOR_SOURCE_DIR`, `CASCOR_CONFIG_DIR`). `ConfigManager._apply_environment_overrides()` treats ALL `CASCOR_*` env vars as config overrides, splitting on `_` to create nested config paths. This corrupts unrelated YAML config nodes and produces spurious warnings.

### RC-4 (MINOR): `CASCOR_DEMO_MODE` Value Convention Mismatch in `./demo` Script

**Severity**: LOW — Masked by CascorIntegration fallback behavior

`./demo` line 141: `export CASCOR_DEMO_MODE="${FALSE}"` uses the bash TRUE=0/FALSE=1 convention. Python `main.py` line 196 checks for `"1"`, `"true"`, `"True"`, `"yes"`, `"Yes"`. The value `"1"` (bash FALSE) accidentally matches Python's expected "enable" value. The intent and the code are misaligned even if the result happens to work. The variable name `FALSE` suggests "disable demo mode" but the exported value `"1"` enables it in Python.

---

## Fixes Designed

### Fix 1: Script-Level JuniperData Service Management (Addresses RC-1)

**Approach**: Modify `./try` and `./demo` scripts to ensure JuniperData is available before launching Canopy. This follows the same pattern already used for CasCor backend management in `./try` (lines 91-103).

**Rationale**: Lowest-risk, highest-impact fix. Preserves the architectural boundary (datasets from JuniperData via HTTP) while making `./try` and `./demo` self-sufficient.

#### 1a. Export `JUNIPER_DATA_URL` in Both Scripts

Add before the Canopy launch in both `./try` and `./demo`:

```bash
export JUNIPER_DATA_URL="${JUNIPER_DATA_URL:-http://localhost:8100}"
```

#### 1b. Add JuniperData Health Check and Auto-Start

Add a new section in both scripts (after conda activation, before Canopy launch):

```bash
#####################################################################################################################################################################################################
# Ensure JuniperData service is available
#####################################################################################################################################################################################################
JUNIPER_DATA_HEALTH="${JUNIPER_DATA_URL}/v1/health/ready"
log_info "Checking JuniperData service at ${JUNIPER_DATA_URL}"

if ! curl -fsS --max-time 3 "${JUNIPER_DATA_HEALTH}" >/dev/null 2>&1; then
    log_info "JuniperData service not running, starting..."
    nohup "${LANGUAGE_PATH}" -m juniper_data --port 8100 > "${LOGS_DIR}/juniper_data.log" 2>&1 &
    JUNIPER_DATA_PID="$!"
    log_info "JuniperData launched with PID: ${JUNIPER_DATA_PID}"

    # Wait for service readiness (up to 30 seconds)
    RETRIES=0
    MAX_RETRIES=30
    while [ "${RETRIES}" -lt "${MAX_RETRIES}" ]; do
        if curl -fsS --max-time 2 "${JUNIPER_DATA_HEALTH}" >/dev/null 2>&1; then
            log_info "JuniperData service ready"
            break
        fi
        RETRIES=$((RETRIES + 1))
        sleep 1
    done

    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        log_error "JuniperData service failed to start within ${MAX_RETRIES}s"
        kill -TERM "${JUNIPER_DATA_PID}" 2>/dev/null
        exit $(( FALSE ))
    fi
else
    log_info "JuniperData service already running"
    JUNIPER_DATA_PID=""
fi
```

Add cleanup at script exit:

```bash
# Cleanup: stop JuniperData if we started it
if [ -n "${JUNIPER_DATA_PID}" ]; then
    log_info "Stopping JuniperData (PID: ${JUNIPER_DATA_PID})"
    kill -TERM "${JUNIPER_DATA_PID}" 2>/dev/null
fi
```

**Prerequisite**: JuniperData must be importable. Ensure `juniper-data` (the service package) is installed in the conda environment. Add a script-level check:

```bash
if ! "${LANGUAGE_PATH}" -c "import juniper_data" 2>/dev/null; then
    log_error "juniper-data package not installed."
    log_error "Install with: pip install -e /path/to/JuniperData/juniper_data/"
    exit $(( FALSE ))
fi
```

#### 1c. Add Startup Validation in `main.py` Lifespan

In `main.py` lifespan function, before `get_demo_mode()`, add a pre-flight check:

```python
# Validate JuniperData availability before initializing demo mode
juniper_data_url = os.environ.get("JUNIPER_DATA_URL")
if not juniper_data_url:
    # Try config fallback (app_config.yaml backend.juniper_data.url)
    config_url = config.get("backend.juniper_data.url")
    if config_url and not config_url.startswith("$"):
        os.environ["JUNIPER_DATA_URL"] = config_url
        juniper_data_url = config_url
        system_logger.info(f"JUNIPER_DATA_URL set from config: {juniper_data_url}")

if not juniper_data_url:
    system_logger.error(
        "JUNIPER_DATA_URL not configured. JuniperData is required for dataset generation.\n"
        "Set JUNIPER_DATA_URL=http://localhost:8100 and ensure JuniperData is running.\n"
        "Use ./demo or ./try scripts which handle this automatically."
    )
    raise RuntimeError("JUNIPER_DATA_URL not configured")
```

---

### Fix 2: Implement `${VAR:default}` Config Expansion (Addresses RC-2)

**Approach**: Replace `os.path.expandvars()` in `ConfigManager._expand_env_vars()` with custom expansion that supports `${VAR:default_value}` syntax.

```python
import re

_DEFAULT_PATTERN = re.compile(r'\$\{([^}:]+):([^}]*)\}')

def _expand_env_vars(self):
    """Recursively expand environment variables in configuration values.

    Supports:
        - ${VAR} - expand, empty string if unset
        - $VAR - expand, empty string if unset
        - ${VAR:default} - expand, use default if unset or empty
    """
    def expand_value(value):
        if isinstance(value, str):
            # First handle ${VAR:default} syntax (not supported by os.path.expandvars)
            def replace_with_default(match):
                var_name = match.group(1)
                default_val = match.group(2)
                return os.environ.get(var_name) or default_val

            value = _DEFAULT_PATTERN.sub(replace_with_default, value)
            # Then handle standard $VAR and ${VAR} syntax
            return os.path.expandvars(value)
        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [expand_value(item) for item in value]
        return value

    self.config = expand_value(self.config)
    self.logger.debug("Environment variables expanded in configuration")
```

This fix also resolves the trailing `}` in the backend path, because `${CASCOR_BACKEND_PATH:../../JuniperCascor/juniper_cascor}` will now correctly expand to the default value when unset.

---

### Fix 3: Filter Shell-Only `CASCOR_*` Variables from Config Overrides (Addresses RC-3)

**Approach**: Add an exclusion set to `_apply_environment_overrides()` to skip `CASCOR_*` env vars that are shell-only and not intended as config overrides.

```python
# Shell-only CASCOR_* variables exported by juniper_canopy.conf that are NOT config overrides
_SHELL_ONLY_VARS = frozenset({
    "CASCOR_MAIN_FILE",
    "CASCOR_MAIN_FILE_NAME",
    "CASCOR_SOURCE_DIR",
    "CASCOR_SOURCE_DIR_NAME",
    "CASCOR_CONFIG_DIR",
    "CASCOR_SOURCE_PATH",
    "CASCOR_PATH",
    "CASCOR_PARENT_PATH",
    "CASCOR_NAME",
    "CASCOR_PROCESS_NAME",
    "CASCOR_SCRIPT_SOURCE_DIR",
    "CASCOR_SCRIPT_APPLICATION_DIR",
    "CASCOR_SCRIPT_CONF_DIR",
    "CASCOR_SCRIPT_SUBPROJECT_DIR",
})

def _apply_environment_overrides(self):
    prefix = "CASCOR_"
    for env_var, value in os.environ.items():
        if env_var.startswith(prefix) and env_var not in _SHELL_ONLY_VARS:
            # ... existing override logic
```

**Alternative Options Considered**:

- **Option B (Allowlist)**: Only apply overrides for env vars that match known config paths. Safer but requires maintenance.
- **Option C (Different prefix)**: Use `CANOPY_` prefix for Canopy-specific config overrides to avoid collision with CasCor shell variables entirely. Larger change but eliminates the problem class.

**Recommendation**: Option A (exclusion set) for immediate fix, with Option C evaluated for a future release.

---

### Fix 4: Fix `CASCOR_DEMO_MODE` Value in `./demo` Script (Addresses RC-4)

**Approach**: Change the export in `./demo` (line 141) and `util/juniper_canopy-demo.bash` (line 141) from:

```bash
export CASCOR_DEMO_MODE="${FALSE}"
```

to:

```bash
export CASCOR_DEMO_MODE="1"
```

The Python code checks for `"1"`, `"true"`, etc. Using `"1"` is explicit and unambiguous. The bash TRUE/FALSE convention (`0`/`1`) is the inverse of Python's truthy convention, which makes `${FALSE}` confusing when the intent is to enable demo mode.

---

### Fix 5: Make `demo_mode.py` Read `JUNIPER_DATA_URL` from Config as Fallback (Defense-in-depth for RC-1)

Currently `_generate_spiral_dataset()` only checks `os.environ.get("JUNIPER_DATA_URL")`. After Fix 2, the config will have a properly-resolved default. The code should check config as a fallback:

```python
def _generate_spiral_dataset(self, n_samples: int = 200, algorithm: Optional[str] = None) -> Dict[str, Any]:
    juniper_data_url = os.environ.get("JUNIPER_DATA_URL")

    if not juniper_data_url:
        # Try config fallback (app_config.yaml backend.juniper_data.url)
        config_mgr = ConfigManager()
        config_url = config_mgr.config.get("backend", {}).get("juniper_data", {}).get("url")
        if config_url and not config_url.startswith("$"):
            juniper_data_url = config_url
            self.logger.info(f"Using JUNIPER_DATA_URL from config: {juniper_data_url}")

    if not juniper_data_url:
        from juniper_data_client.exceptions import JuniperDataConfigurationError
        raise JuniperDataConfigurationError(...)

    self.logger.info(f"Fetching dataset from JuniperData at {juniper_data_url}")
    return self._generate_spiral_dataset_from_juniper_data(n_samples, juniper_data_url, algorithm=algorithm)
```

---

## Alternative Approaches Evaluated

### Alternative A: Install JuniperData as a Dependency

**Assessment**: Good supporting move but not sufficient alone. Even if `juniper-data` is installed (making `python -m juniper_data` available), the service still needs to be running and `JUNIPER_DATA_URL` still needs to be set. This approach is a **prerequisite** for Fix 1b (auto-start in scripts).

**Recommendation**: Adopt as a dev convenience — ensure `juniper-data` is listed as a dev dependency and installable. Required for auto-start to work.

### Alternative B: Import JuniperData Package Directly (In-Process)

**Assessment**: Two sub-approaches:

- **B1 (Direct generator call)**: Conflicts with the design that all datasets come from JuniperData via API. Reintroduces "local generation" in spirit, even if using JuniperData code. Breaks the service boundary, harms test isolation, creates prod/dev mismatch.
- **B2 (In-process TestClient/ASGITransport)**: Preserves API boundary but adds significant complexity. The current client uses `requests` (network IO); in-process calls would need `httpx` with `ASGITransport` or a transport injection layer. Lifecycle management (startup events, storage, port config) adds fragility. Best suited for integration tests (CAN-INT-018), not runtime.

**Recommendation**: Not recommended for runtime. Consider B2 only for optional integration tests.

### Alternative C: Auto-Launch JuniperData from Python (Subprocess in `main.py`)

**Assessment**: Viable but higher complexity than script-level management. Requires subprocess lifecycle management, signal handling, port collision detection, logging coordination, and cleanup. Only warranted if developers frequently bypass `./try`/`./demo` to run `uvicorn main:app` directly.

**Recommendation**: Defer. If needed later, add as optional `development.juniper_data.auto_start: true` config flag. For now, script-level approach (Fix 1b) is simpler and matches existing CasCor management pattern in `./try`.

### Recommended Hybrid Approach

The recommended approach combines **Fix 1 (script-level management)** as the primary mechanism with **Fix 2 (config expansion)** and **Fix 1c/5 (in-app validation)** as defense-in-depth layers:

1. Scripts ensure JuniperData is running (same pattern as CasCor in `./try`)
2. Config defaults work correctly when env vars are unset
3. `main.py` validates early and fails with actionable guidance
4. `demo_mode.py` checks config as fallback before raising

---

## Additional Tests Needed

### Test Group 1: Startup Regression Tests

**Location**: `src/tests/regression/test_startup_regression.py`

| ID   | Test                                                  | Validates                                        |
| ---- | ----------------------------------------------------- | ------------------------------------------------ |
| ST-1 | `test_demo_mode_init_with_juniper_data_url_set`       | DemoMode initializes when JUNIPER_DATA_URL set   |
| ST-2 | `test_demo_mode_init_without_juniper_data_url_raises` | Clear error when JUNIPER_DATA_URL missing        |
| ST-3 | `test_demo_mode_init_with_config_fallback`            | Config URL used when env var missing (Fix 5)     |
| ST-4 | `test_app_lifespan_validates_juniper_data_url`        | Lifespan pre-flight check works (Fix 1c)         |
| ST-5 | `test_app_startup_with_mocked_juniper_data`           | Full startup succeeds with mock client           |
| ST-6 | `test_demo_mode_dataset_has_correct_schema`           | Dataset from JuniperData matches expected schema |

```python
# Example: ST-2
@pytest.mark.regression
@pytest.mark.unit
def test_demo_mode_init_without_juniper_data_url_raises(reset_singletons, monkeypatch):
    """Regression test: DemoMode raises clear error without JUNIPER_DATA_URL."""
    monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)
    from juniper_data_client.exceptions import JuniperDataConfigurationError

    with pytest.raises(JuniperDataConfigurationError, match="JUNIPER_DATA_URL"):
        from demo_mode import DemoMode
        DemoMode(update_interval=1.0)
```

### Test Group 2: Config Expansion Tests

**Location**: `src/tests/unit/test_config_expansion.py` or extend `src/tests/unit/test_config_refactoring.py`

| ID   | Test                                             | Validates                                        |
| ---- | ------------------------------------------------ | ------------------------------------------------ |
| CE-1 | `test_expand_env_var_with_default_unset`         | `${VAR:default}` returns default when VAR unset  |
| CE-2 | `test_expand_env_var_with_default_set`           | `${VAR:default}` returns VAR value when set      |
| CE-3 | `test_expand_env_var_without_default`            | `${VAR}` returns empty when unset (standard)     |
| CE-4 | `test_expand_nested_config_with_defaults`        | Full config tree expansion with defaults works   |
| CE-5 | `test_backend_path_no_trailing_brace`            | Expanded path never contains literal `}`         |
| CE-6 | `test_juniper_data_url_resolved_from_config`     | Config URL resolves correctly to default         |

```python
# Example: CE-1
@pytest.mark.unit
def test_expand_env_var_with_default_unset(monkeypatch):
    """Config ${VAR:default} syntax returns default when env var is unset."""
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
    config_mgr = ConfigManager.__new__(ConfigManager)
    config_mgr.config = {"test_key": "${NONEXISTENT_VAR:fallback_value}"}
    config_mgr.logger = logging.getLogger("test")
    config_mgr._expand_env_vars()
    assert config_mgr.config["test_key"] == "fallback_value"

# Example: CE-5
@pytest.mark.regression
@pytest.mark.unit
def test_backend_path_no_trailing_brace(monkeypatch):
    """Backend path expansion must not leave trailing } character."""
    monkeypatch.delenv("CASCOR_BACKEND_PATH", raising=False)
    config_mgr = ConfigManager()
    backend_path = config_mgr.config.get("backend", {}).get(
        "cascor_integration", {}
    ).get("backend_path", "")
    assert not backend_path.endswith("}")
    assert "${" not in backend_path
```

### Test Group 3: Environment Override Collision Tests

**Location**: `src/tests/unit/test_config_env_override.py` or extend existing config tests

| ID   | Test                                            | Validates                                     |
| ---- | ----------------------------------------------- | --------------------------------------------- |
| EO-1 | `test_shell_only_cascor_vars_excluded`          | `CASCOR_MAIN_FILE` etc. don't corrupt config  |
| EO-2 | `test_valid_cascor_overrides_still_applied`     | `CASCOR_DEMO_MODE` etc. still work            |
| EO-3 | `test_no_collision_warnings_with_shell_vars`    | No warnings logged for excluded vars          |

```python
# Example: EO-1
@pytest.mark.unit
def test_shell_only_cascor_vars_excluded(monkeypatch, caplog):
    """Shell-only CASCOR_* vars do not corrupt config structure."""
    monkeypatch.setenv("CASCOR_MAIN_FILE", "/some/path/main.py")
    monkeypatch.setenv("CASCOR_SOURCE_DIR", "/some/path/src")
    config_mgr = ConfigManager()
    assert "override collision" not in caplog.text
```

### Test Group 4: CASCOR_DEMO_MODE Value Interpretation Tests

**Location**: `src/tests/unit/test_demo_mode_activation.py` or extend existing main.py tests

| ID   | Test                                            | Validates                                       |
| ---- | ----------------------------------------------- | ----------------------------------------------- |
| DM-1 | `test_cascor_demo_mode_1_activates_demo`        | `CASCOR_DEMO_MODE=1` → demo mode active         |
| DM-2 | `test_cascor_demo_mode_true_activates_demo`     | `CASCOR_DEMO_MODE=true` → demo mode active      |
| DM-3 | `test_cascor_demo_mode_0_does_not_activate`     | `CASCOR_DEMO_MODE=0` → demo mode NOT forced     |
| DM-4 | `test_cascor_demo_mode_unset_does_not_activate` | No `CASCOR_DEMO_MODE` → demo mode NOT forced    |

### Test Group 5: Script Smoke Tests (Optional / CI)

**Location**: `src/tests/e2e/test_startup_scripts.py`

| ID   | Test                                        | Validates                              |
| ---- | ------------------------------------------- | -------------------------------------- |
| SS-1 | `test_demo_script_exports_juniper_data_url` | `./demo` sets JUNIPER_DATA_URL in env  |
| SS-2 | `test_try_script_exports_juniper_data_url`  | `./try` sets JUNIPER_DATA_URL in env   |
| SS-3 | `test_demo_script_sets_cascor_demo_mode_1`  | `./demo` sets CASCOR_DEMO_MODE to "1"  |

These would require `subprocess`-based execution or shell parsing; mark with `@pytest.mark.e2e`.

---

## Implementation Priority

| Priority | Fix          | RC Addressed | Effort | Impact                                    |
| -------- | ------------ | ------------ | ------ | ----------------------------------------- |
| P0       | Fix 1a       | RC-1         | XS     | Unblocks startup (env var export)         |
| P0       | Fix 1b       | RC-1         | S      | Auto-starts JuniperData (self-sufficient) |
| P0       | Fix 4        | RC-4         | XS     | Correct demo mode activation value        |
| P1       | Fix 2        | RC-2         | S      | Config defaults work correctly            |
| P1       | Fix 1c       | RC-1         | S      | Fail-fast with actionable message         |
| P1       | Fix 5        | RC-1         | XS     | Defense-in-depth for config fallback      |
| P2       | Fix 3        | RC-3         | S      | Eliminates noisy collision warnings       |
| P2       | Test Group 1 | RC-1         | M      | Regression guard for startup              |
| P2       | Test Group 2 | RC-2         | S      | Regression guard for config expansion     |
| P3       | Test Group 3 | RC-3         | S      | Regression guard for override collisions  |
| P3       | Test Group 4 | RC-4         | S      | Regression guard for demo mode activation |
| P3       | Test Group 5 | All          | M      | End-to-end script validation (CI)         |

---

## References

- [CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md](CANOPY_JUNIPER_DATA_INTEGRATION_PLAN.md) — Integration plan document (CAN-INT-002: mandatory URL)
- `src/demo_mode.py:360-385` — `_generate_spiral_dataset()` (regression location)
- `src/main.py:105-217` — Lifespan and demo mode initialization
- `src/config_manager.py:112-159` — Env var expansion and overrides
- `conf/app_config.yaml:268-283` — JuniperData config section with `${VAR:default}` syntax
- `conf/juniper_canopy.conf:350-384` — Shell CASCOR_* variable exports causing collisions
- Commit `33987d2` — Regression-introducing commit (removed local fallback)
- Commit `a1e89f8` — Original JuniperData integration (with fallback)

---

## Document History

| Date       | Author   | Changes                                                            |
| ---------- | -------- | ------------------------------------------------------------------ |
| 2026-02-09 | AI Agent | Initial regression analysis: 4 root causes, 5 fixes, 5 test groups |

---
