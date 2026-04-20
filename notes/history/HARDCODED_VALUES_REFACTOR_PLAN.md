# Hardcoded Values Refactor Plan — juniper-canopy

**Version**: 0.4.0
**Created**: 2026-04-08
**Status**: PLANNING — No source code modifications
**Companion Document**: `HARDCODED_VALUES_ANALYSIS.md`

---

## Phase 1: Constants Infrastructure (Priority: HIGH)

### Step 1.1: Extend `canopy_constants.py`

**Task**: Add two new constants classes to the existing `src/canopy_constants.py`:

**`SecurityConstants`** (~10 constants):

- `MAX_REQUEST_BODY_BYTES`
- `DEFAULT_CSP_POLICY`
- `EXEMPT_PATH_PREFIXES`
- `EXEMPT_SECURITY_PATHS`
- `CORS_LOCAL_ORIGIN`

**`BackendConstants`** (~10 constants):

- `DEFAULT_CASCOR_SERVICE_URL`
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD`
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`
- `REDIS_SOCKET_TIMEOUT`
- `REDIS_CONNECT_TIMEOUT`
- `CASSANDRA_CONNECT_TIMEOUT`
- `MAX_METRICS_BUFFER_SIZE`
- `DEMO_THREAD_JOIN_TIMEOUT`
- `DEMO_MAIN_LOOP_SLEEP`

### Step 1.2: Extend Existing Classes

**`DashboardConstants`** — Add:

- `POST_TIMEOUT`, `GET_TIMEOUT`, `LONG_POST_TIMEOUT`, `TIMEOUT_THRESHOLD`

**`ServerConstants`** — Add:

- `DISCOVERY_HOST`, `DISCOVERY_PORTS`, `DISCOVERY_TIMEOUT`, `HEALTH_LIVE_ENDPOINT`

---

## Phase 2: Source File Refactor (Priority: HIGH)

### Step 2.1: Refactor Middleware

**File**: `src/middleware.py` — 4 replacements

### Step 2.2: Refactor Service Discovery

**File**: `src/discovery.py` — 4 replacements

### Step 2.3: Refactor Backend Adapters

**Files**: `src/backend/cascor_service_adapter.py`, `src/backend/redis_client.py`, `src/backend/cassandra_client.py`, `src/backend/training_monitor.py` — 7 replacements

### Step 2.4: Refactor Dashboard Manager

**File**: `src/frontend/dashboard_manager.py` — 4 replacements

### Step 2.5: Refactor Demo Mode

**File**: `src/demo_mode.py` — 2 replacements

### Step 2.6: Refactor Dataset Plotter

**File**: `src/frontend/components/dataset_plotter.py` — 1 replacement (CORS origin)

---

## Phase 3: Validation (Priority: HIGH)

### Step 3.1: Run Full Test Suite

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperCanopy
pytest -m "unit and not slow" -v
```

### Step 3.2: Pre-commit Hooks
### Step 3.3: Verify Demo Mode

Start demo mode and verify dashboard loads correctly with all visualizations.

---

## Phase 4: Documentation & Release (Priority: MEDIUM)

### Step 4.1: Update AGENTS.md — Document new `SecurityConstants` and `BackendConstants` classes
### Step 4.2: Update CHANGELOG.md
### Step 4.3: Create Release Description
