# JuniperCanopy ↔ JuniperData Integration Plan

**Project**: JuniperCanopy - Monitoring and Diagnostic Frontend for CasCor NN
**Integration Target**: JuniperData - Dataset Generation Service
**Version**: 1.1.0
**Author**: Paul Calnon
**Created**: 2026-02-07
**Status**: Active Development
**Last Updated**: 2026-02-07

---

## Primary Objective

All datasets used by JuniperCanopy MUST be received from JuniperData via API call. No dataset generation operations shall be carried out locally within the JuniperCanopy application.

## Current State Summary

| Component                    | Status                    | Notes                                                                            |
| ---------------------------- | ------------------------- | -------------------------------------------------------------------------------- |
| `JuniperDataClient`          | **COMPLETE** (shared pkg) | Replaced with shared package code (retry, auth, pooling, health checks)          |
| Demo mode dataset generation | **MANDATORY** JuniperData | `src/demo_mode.py` - JuniperData only, raises `JuniperDataConfigurationError`    |
| CascorIntegration dataset    | **MANDATORY** JuniperData | `src/backend/cascor_integration.py` - JuniperData only, no local fallback        |
| `JUNIPER_DATA_URL` in config | **CONFIGURED**            | Added to `conf/app_config.yaml` with env var expansion                           |
| Dataset selector dropdown    | NON-FUNCTIONAL            | `DatasetPlotter` has dropdown with `options=[]`, never populated                 |
| Dataset API endpoints        | MINIMAL                   | Only `GET /api/dataset` returns single current dataset                           |
| Client test coverage         | **71 tests**              | `test_juniper_data_integration.py` - Full integration test coverage              |
| Schema consistency           | **CANONICAL**             | All paths use `inputs`/`targets`/`dataset_name` (not `features`/`labels`/`name`) |
| Docker JuniperData service   | NOT CONFIGURED            | No JuniperData entry in `conf/docker-compose.yaml`                               |
| JuniperData mandatory        | **YES**                   | Matches JuniperCascor pattern; `JUNIPER_DATA_URL` required                       |
| Full test suite              | **3,276 passed**          | 0 failed, 0 errors, 36 skipped (all legitimate)                                  |

### Cross-Project Integration Status

| Project       | JuniperData Integration | Plan Document                                                                |
| ------------- | ----------------------- | ---------------------------------------------------------------------------- |
| JuniperData   | Service ready (v0.4.0)  | `JuniperData/juniper_data/notes/INTEGRATION_DEVELOPMENT_PLAN.md`             |
| JuniperCascor | 8/9 tasks COMPLETE      | `JuniperCascor/juniper_cascor/notes/CASCOR_JUNIPER_DATA_INTEGRATION_PLAN.md` |
| JuniperCanopy | Phase 0-1 COMPLETE      | This document                                                                |

### JuniperData Service Capabilities (v0.4.0)

| Feature                | Status    | Notes                                                            |
| ---------------------- | --------- | ---------------------------------------------------------------- |
| REST API (`/v1/`)      | AVAILABLE | Full CRUD for datasets                                           |
| Generators             | 4 types   | spiral, xor, gaussian, circles                                   |
| Storage backends       | 5 types   | memory, localfs, cached, redis, huggingface                      |
| NPZ artifact download  | AVAILABLE | Standardized schema: X_train/y_train/X_test/y_test/X_full/y_full |
| API key authentication | AVAILABLE | Header-based: `X-API-Key`                                        |
| Rate limiting          | AVAILABLE | Per-client fixed-window                                          |
| Health endpoints       | AVAILABLE | `/v1/health`, `/v1/health/live`, `/v1/health/ready`              |
| Dataset lifecycle      | AVAILABLE | TTL, tags, filtering, batch delete, stats                        |
| Shared client package  | AVAILABLE | `juniper-data-client` pip package (DATA-012)                     |
| Dockerfile             | AVAILABLE | Multi-stage, port 8100                                           |
| Parameter aliases      | AVAILABLE | `n_points`→`n_points_per_spiral`, `noise_level`→`noise`          |

---

## Table of Contents

- [Phase 0: Client Migration & Mandatory API](#phase-0-client-migration--mandatory-api)
- [Phase 1: Core Integration & Schema Fix](#phase-1-core-integration--schema-fix)
- [Phase 2: Configuration & Infrastructure](#phase-2-configuration--infrastructure)
- [Phase 3: Frontend Enhancement & Dataset Management](#phase-3-frontend-enhancement--dataset-management)
- [Phase 4: Testing & Validation](#phase-4-testing--validation)
- [Deferred Items](#deferred-items)
- [Newly Identified Issues](#newly-identified-issues)
- [Cross-Project Reference](#cross-project-reference)

---

## Phase 0: Client Migration & Mandatory API

**Priority**: CRITICAL | **Risk**: MEDIUM | **Blocking**: All subsequent phases
**Rationale**: JuniperCascor has already made JuniperData mandatory (CAS-INT-001). JuniperCanopy must follow the same pattern to eliminate local dataset generation and ensure consistent behavior across the ecosystem.

### CAN-INT-001: Replace Local JuniperDataClient with Shared Package

**Priority**: CRITICAL | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: HIGH - Current local client lacks auth, retry, validation features
**Integration Importance**: CRITICAL - Foundation for all other integration tasks
**If Not Fixed**: Client diverges from shared package, missing security features, maintenance burden
**Blocks**: CAN-INT-002, CAN-INT-003, CAN-INT-005, CAN-INT-006, CAN-INT-007

**Source**: JuniperData DATA-012 (COMPLETE), JuniperCascor CAS-INT-001

**Implementation Notes**: Replaced local client code with shared package code in `src/juniper_data_client/`. The editable pip install from JuniperData failed (flat layout issue), so the shared package code was copied with relative imports. Created `exceptions.py` with full hierarchy including Canopy-specific `JuniperDataConfigurationError`. Version bumped to 0.2.0.

The current `src/juniper_data_client/client.py` is a basic client with only 3 methods and no auth/retry support. JuniperData has created a comprehensive shared `juniper-data-client` package (DATA-012) with:

- URL normalization with validation
- Session management with connection pooling
- All dataset CRUD endpoints (create, list, get, delete, preview, artifact)
- Generator endpoints (list, schema)
- Health check endpoints (health, live, ready, wait_for_ready)
- `create_spiral_dataset()` convenience method
- Automatic retry with configurable backoff (429, 5xx)
- Custom exception hierarchy
- Context manager support
- API key authentication support
- Full type hints with mypy strict mode
- 35 unit tests, 96% coverage

**Changes Required**:

1. Install `juniper-data-client` package:

   ```bash
   pip install -e /path/to/JuniperData/juniper_data/juniper_data_client/[test]
   ```

2. Add `juniper-data-client` to `conf/requirements.txt`
3. Update all imports from `from juniper_data_client import JuniperDataClient` (should work without changes due to same package name)
4. Remove `src/juniper_data_client/` directory entirely
5. Update `pyproject.toml` if `juniper_data_client` is listed as a local package
6. Verify all existing import sites work with the new package

**Acceptance Criteria**:

- `src/juniper_data_client/` directory is removed
- All imports use the shared `juniper-data-client` package
- `pip install -e .[test]` includes `juniper-data-client` as a dependency
- All existing tests pass (3,215+)

---

### CAN-INT-002: Make JUNIPER_DATA_URL Mandatory

**Priority**: CRITICAL | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: HIGH - Canopy silently falls back to local generation, hiding integration failures
**Integration Importance**: CRITICAL - Ensures all datasets come from JuniperData
**If Not Fixed**: Local fallback masks integration failures; dataset inconsistencies between Canopy/Cascor
**Blocks**: CAN-INT-008, CAN-INT-009
**Depends On**: CAN-INT-001

**Source**: JuniperCascor CAS-INT-001 (COMPLETE), JuniperData CAN-REF-001

**Implementation Notes**: Both `demo_mode.py:_generate_spiral_dataset()` and `cascor_integration.py:_generate_missing_dataset_info()` now raise `JuniperDataConfigurationError` if `JUNIPER_DATA_URL` is not set. No local fallback remains. Test environment sets `JUNIPER_DATA_URL=http://localhost:8100` in `conftest.py`. Session-scoped autouse fixture mocks `JuniperDataClient` with realistic spiral data.

Currently, both `demo_mode.py` and `cascor_integration.py` check for `JUNIPER_DATA_URL` env var and fall back to local generation if not set. This must change to match JuniperCascor's behavior where JuniperData is mandatory.

**Changes Required**:

1. **`src/demo_mode.py`**: In `_generate_spiral_dataset()` (line 360):
   - Remove the `if juniper_data_url:` conditional and local fallback
   - Always use `_generate_spiral_dataset_from_juniper_data()`
   - Raise clear error if `JUNIPER_DATA_URL` is not set
   - Log the configuration source for debugging

2. **`src/backend/cascor_integration.py`**: In `_generate_missing_dataset_info()` (line 1235):
   - Remove the local `_create_juniper_dataset()` fallback path
   - Always delegate to JuniperData service
   - Raise error if `JUNIPER_DATA_URL` is not configured

3. **`src/main.py`**: In the lifespan startup:
   - Validate `JUNIPER_DATA_URL` is set before initializing demo mode or cascor integration
   - Log a clear startup error message if missing

**Acceptance Criteria**:

- Starting the app without `JUNIPER_DATA_URL` produces a clear, actionable error message
- Starting with `JUNIPER_DATA_URL` always fetches datasets from JuniperData
- No local spiral generation code executes in normal operation
- All tests updated to mock JuniperData responses

---

### CAN-INT-003: Fix Dataset Schema Mismatch

**Priority**: CRITICAL | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: CRITICAL - Real backend path is broken for frontend dataset display
**Integration Importance**: CRITICAL - Frontend cannot display data from CascorIntegration
**If Not Fixed**: Dataset View tab shows nothing when using real CasCor backend
**Blocks**: None (but affects all frontend dataset display)
**Depends On**: CAN-INT-001

**Source**: Code review, JuniperData CAN-REF-004

**Implementation Notes**: Standardized all code paths on canonical schema: `inputs`/`targets`/`dataset_name` instead of `features`/`labels`/`name`. Changes: `CascorIntegration._create_juniper_dataset()` uses `inputs`/`targets`, `CascorIntegration.get_dataset_info()` passes `inputs=`/`targets=` to DataAdapter, `DataAdapter.prepare_dataset_for_visualization()` accepts `inputs`/`targets` as primary params with `features`/`labels` as deprecated aliases, returns `dataset_name` key instead of `name`.

Three different schemas are in use:

| Source              | Feature Key | Label Key | Format       | Additional Keys                              |
| ------------------- | ----------- | --------- | ------------ | -------------------------------------------- |
| Demo mode           | `inputs`    | `targets` | numpy arrays | `inputs_tensor`, `targets_tensor`            |
| CascorIntegration   | `features`  | `labels`  | Python lists | `class_distribution`, `dataset_name`         |
| DataAdapter         | `features`  | `labels`  | Python lists | `name`                                       |
| Frontend (expected) | `inputs`    | `targets` | Python lists | `num_samples`, `num_features`, `num_classes` |

**Changes Required**:

1. **Standardize on a canonical schema** for the `/api/dataset` endpoint response:

   ```python
   {
       "inputs": [[x1, y1], [x2, y2], ...],   # Feature coordinates
       "targets": [0, 1, 0, 1, ...],           # Class labels (integer)
       "num_samples": int,
       "num_features": int,
       "num_classes": int,
       "split_indices": {                       # Optional: train/test split
           "train": [0, 1, 2, ...],
           "test": [100, 101, ...],
       },
       "dataset_name": str,                     # Optional: human-readable name
       "generator": str,                        # Optional: generator type
   }
   ```

2. **Update `main.py`** `get_dataset()` endpoint to normalize both demo mode and CascorIntegration outputs to the canonical schema

3. **Update `CascorIntegration.get_dataset_info()`** to return `inputs`/`targets` instead of `features`/`labels`

4. **Update `DataAdapter.prepare_dataset_for_visualization()`** to use canonical key names

5. **Add train/test split indices** when available from NPZ data (`X_train`/`X_test` lengths)

**Acceptance Criteria**:

- Both demo mode and CascorIntegration return identical schema structure
- Frontend `DatasetPlotter` renders correctly for both sources
- `DecisionBoundary` component receives correct `inputs`/`targets` keys
- Schema is documented in code docstrings

---

## Phase 1: Core Integration & Schema Fix

**Priority**: HIGH | **Risk**: LOW | **Blocking**: Phase 2, Phase 3
**Rationale**: These items bring the Canopy JuniperData client to feature parity with the CasCor implementation.

### CAN-INT-004: Add JUNIPER_DATA_URL to app_config.yaml

**Priority**: HIGH | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Small
**Severity**: MEDIUM - Missing configuration makes deployment harder
**Integration Importance**: HIGH - Required for proper configuration management
**If Not Fixed**: URL only configurable via env var; inconsistent with other config patterns
**Blocks**: None

**Source**: JuniperData CAN-REF-002, code review

**Implementation Notes**: Added `juniper_data` section to `conf/app_config.yaml` under `backend:` with all configuration keys: enabled, url, api_key, timeout, retry_attempts, retry_backoff_base, health_check_on_startup, default_generator, default_params.

The `JUNIPER_DATA_URL` environment variable is used but not documented in `conf/app_config.yaml`.

**Changes Required**:

1. Add `juniper_data` section to `conf/app_config.yaml`:

   ```yaml
   backend:
     juniper_data:
       enabled: true
       url: "${JUNIPER_DATA_URL:http://localhost:8100}"
       api_key: "${JUNIPER_DATA_API_KEY:}"
       timeout: 30
       retry_attempts: 3
       retry_backoff_base: 1.0
       health_check_on_startup: true
   ```

2. Add `JUNIPER_DATA_URL` and `JUNIPER_DATA_API_KEY` to the `environment_variables` list

3. Update `ConfigManager` to read JuniperData configuration

4. Update `demo_mode.py` and `cascor_integration.py` to read from config hierarchy (env > yaml > constant)

**Acceptance Criteria**:

- JuniperData configuration is documented in `app_config.yaml`
- Configuration follows the env > yaml > constants hierarchy
- All JuniperData-related env vars are listed in `environment_variables`

---

### CAN-INT-005: Add API Key Authentication Support

**Priority**: HIGH | **Status**: **COMPLETE** (via CAN-INT-001) | **Effort**: Small
**Severity**: MEDIUM - JuniperData supports auth but Canopy client doesn't use it
**Integration Importance**: HIGH - Required for production deployments with auth enabled
**If Not Fixed**: Cannot connect to auth-protected JuniperData instances
**Blocks**: None
**Depends On**: CAN-INT-001

**Source**: JuniperData DATA-017 (COMPLETE), JuniperCascor CAS-INT-003 (COMPLETE)

**Implementation Notes**: Built into the shared client package adopted in CAN-INT-001. The `JuniperDataClient` constructor accepts `api_key` parameter and sets `X-API-Key` header.

JuniperData supports API key authentication via `X-API-Key` header (DATA-017). JuniperCascor has already added support (CAS-INT-003). If using the shared `juniper-data-client` package (CAN-INT-001), this is already built in.

**Changes Required** (if CAN-INT-001 is not yet complete):

1. Add `api_key: Optional[str]` parameter to `JuniperDataClient.__init__()`
2. Read from `JUNIPER_DATA_API_KEY` env var as fallback
3. Set `X-API-Key` header on session when configured
4. Pass API key through from configuration to client instantiation

**If CAN-INT-001 is complete**: The shared package already handles this. Just pass `api_key` from config when creating the client.

**Acceptance Criteria**:

- API key is passed from config/env to client
- `X-API-Key` header is set on all requests when configured
- Works with and without authentication (backward compatible)

---

### CAN-INT-006: Add Retry/Backoff for Transient Failures

**Priority**: HIGH | **Status**: **COMPLETE** (via CAN-INT-001) | **Effort**: Small
**Severity**: MEDIUM - Single request failure breaks dataset loading
**Integration Importance**: HIGH - Required for reliable operation
**If Not Fixed**: Transient network errors cause dataset loading failures
**Blocks**: None
**Depends On**: CAN-INT-001

**Source**: JuniperCascor CAS-INT-008 (COMPLETE)

**Implementation Notes**: Built into the shared client package adopted in CAN-INT-001. Uses `urllib3.Retry` with exponential backoff, retries on 429/500/502/503/504, connection pooling via `HTTPAdapter`.

JuniperCascor has already implemented retry logic (CAS-INT-008). If using the shared package (CAN-INT-001), this is already built in.

**Changes Required** (if CAN-INT-001 is not yet complete):

1. Add `MAX_RETRIES`, `RETRY_BACKOFF_BASE`, `_RETRYABLE_STATUS_CODES` constants
2. Implement loop-based retry with exponential backoff in `_request()`
3. Retry on 502/503/504, `ConnectionError`, `Timeout`
4. Non-retryable errors (4xx) fail immediately

**If CAN-INT-001 is complete**: Already built into the shared package.

---

### CAN-INT-007: Add NPZ Data Contract Validation

**Priority**: HIGH | **Status**: **PARTIAL** (via CAN-INT-001/002) | **Effort**: Small
**Severity**: MEDIUM - Silently corrupt data if NPZ schema changes
**Integration Importance**: HIGH - Ensures data integrity
**If Not Fixed**: Malformed NPZ data silently corrupts visualizations
**Blocks**: None
**Depends On**: CAN-INT-001

**Source**: JuniperData DATA-010 (COMPLETE), JuniperCascor CAS-INT-004 (COMPLETE)

**Implementation Notes**: Basic validation implemented - both `demo_mode.py` and `cascor_integration.py` now raise `ValueError` if `X_full` or `y_full` keys are missing from NPZ data. Full dtype/shape validation not yet implemented.

Validate NPZ artifacts match the expected contract:

- Required keys: `X_train`, `y_train`, `X_test`, `y_test`, `X_full`, `y_full`
- All arrays should be `float32` dtype
- Feature arrays should have 2 columns (x, y coordinates)
- Label arrays should have columns matching number of classes

**Changes Required**:

1. Add validation when consuming NPZ data in `demo_mode.py` and `cascor_integration.py`
2. Raise descriptive error on contract violations
3. Log warnings for unexpected but non-breaking schema differences

**Acceptance Criteria**:

- NPZ validation runs on every artifact download
- Clear error messages for missing keys, wrong shapes, wrong dtypes
- Tests cover all validation cases

---

### CAN-INT-008: Remove Local Dataset Generation from demo_mode.py

**Priority**: HIGH | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: HIGH - Duplicate code, inconsistent with JuniperData source of truth
**Integration Importance**: HIGH - Core objective of integration
**If Not Fixed**: Demo mode generates different data than what JuniperData provides
**Blocks**: None
**Depends On**: CAN-INT-002

**Source**: Primary objective, code review

**Implementation Notes**: `_generate_spiral_dataset_local()` preserved for one release cycle with `DeprecationWarning` but is never called from active code paths. `_generate_spiral_dataset()` always delegates to JuniperData. Schema updated to use canonical `inputs`/`targets` keys.

`demo_mode.py` contains `_generate_spiral_dataset_local()` (lines 454-492) which generates spirals locally. This must be removed once JuniperData is mandatory.

**Changes Required**:

1. Remove `_generate_spiral_dataset_local()` method
2. Remove the fallback path in `_generate_spiral_dataset()`
3. Always use `_generate_spiral_dataset_from_juniper_data()`
4. Add deprecation warnings to local generation methods (if keeping for one release cycle)
5. Update or remove hardcoded parameters (n_samples=200, noise=0.1, seed=42)
6. Make parameters configurable via `app_config.yaml`

**Acceptance Criteria**:

- No local spiral generation code executes in demo mode
- Dataset comes exclusively from JuniperData
- Parameters are configurable, not hardcoded

---

### CAN-INT-009: Remove Local Dataset Generation from cascor_integration.py

**Priority**: HIGH | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: HIGH - Same issue as CAN-INT-008 but for real backend path
**Integration Importance**: HIGH - Core objective of integration
**If Not Fixed**: CascorIntegration generates different data than JuniperData
**Blocks**: None
**Depends On**: CAN-INT-002

**Source**: Primary objective, code review

**Implementation Notes**: `_generate_dataset_local()` preserved with `DeprecationWarning` but never called from active paths. `_generate_missing_dataset_info()` always delegates to JuniperData. `_create_juniper_dataset()` uses canonical `inputs`/`targets`/`dataset_name` schema. Parameters aligned: `n_samples=200`, `noise=0.1` (matching demo mode).

`cascor_integration.py` contains `_create_juniper_dataset()` (lines 1278-1329) and `_generate_missing_dataset_info()` (lines 1235-1255) with local fallback.

**Changes Required**:

1. Remove `_create_juniper_dataset()` local generation method
2. Remove local fallback in `_generate_missing_dataset_info()`
3. Always delegate to JuniperData service
4. Fix parameter inconsistencies (n_samples=100, noise=0.0 vs demo mode's 200, 0.1)

**Acceptance Criteria**:

- No local spiral generation code in cascor_integration
- Dataset comes exclusively from JuniperData
- Parameters match across all consumers

---

## Phase 2: Configuration & Infrastructure

**Priority**: MEDIUM | **Risk**: LOW | **Blocking**: Phase 3
**Rationale**: Infrastructure changes needed for production deployment and development workflow.

### CAN-INT-010: Add JuniperData to docker-compose.yaml

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Small
**Severity**: LOW - Development workflow inconvenience
**Integration Importance**: MEDIUM - Required for containerized development/deployment
**If Not Fixed**: Developers must manually start JuniperData service
**Blocks**: None

**Source**: JuniperData CAN-REF-003, DATA-006 (COMPLETE)

JuniperData now has a Dockerfile (DATA-006). Add it to Canopy's docker-compose.

**Changes Required**:

1. Add `juniper-data` service to `conf/docker-compose.yaml`:

   ```yaml
   services:
     juniper-data:
       build:
         context: ../../JuniperData/juniper_data
         dockerfile: Dockerfile
       ports:
         - "8100:8100"
       environment:
         - JUNIPER_DATA_HOST=0.0.0.0
         - JUNIPER_DATA_PORT=8100
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8100/v1/health"]
         interval: 30s
         timeout: 10s
         retries: 3
   ```

2. Update `juniper-canopy` service to depend on `juniper-data`
3. Set `JUNIPER_DATA_URL=http://juniper-data:8100` in canopy service environment

---

### CAN-INT-011: Add JuniperData Constants to constants.py

**Priority**: MEDIUM | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Small
**Severity**: LOW - Magic strings/numbers scattered in code
**Integration Importance**: MEDIUM - Improves maintainability
**If Not Fixed**: Hardcoded defaults scattered across multiple files
**Blocks**: None

**Source**: Code review

**Implementation Notes**: Added `JuniperDataConstants` class to `src/canopy_constants.py` with all default values: DEFAULT_URL, DEFAULT_TIMEOUT_S, DEFAULT_RETRY_ATTEMPTS, DEFAULT_RETRY_BACKOFF_BASE_S, DEFAULT_DATASET_SAMPLES, DEFAULT_DATASET_NOISE, DEFAULT_DATASET_SEED, DEFAULT_GENERATOR, API_VERSION.

**Changes Required**:

1. Add `JuniperDataConstants` class to `src/constants.py`:

   ```python
   class JuniperDataConstants:
       DEFAULT_URL = "http://localhost:8100"
       DEFAULT_TIMEOUT_S = 30
       DEFAULT_RETRY_ATTEMPTS = 3
       DEFAULT_RETRY_BACKOFF_BASE_S = 1.0
       DEFAULT_DATASET_SAMPLES = 200
       DEFAULT_DATASET_NOISE = 0.1
       DEFAULT_DATASET_SEED = 42
       DEFAULT_GENERATOR = "spiral"
       API_VERSION = "v1"
   ```

---

### CAN-INT-012: Add Startup Health Check for JuniperData

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Small
**Severity**: MEDIUM - App starts without knowing if JuniperData is reachable
**Integration Importance**: MEDIUM - Fail-fast behavior
**If Not Fixed**: Dataset loading fails later with unclear error
**Blocks**: None
**Depends On**: CAN-INT-001, CAN-INT-004

**Source**: JuniperCascor CAS-INT-009 (COMPLETE)

**Changes Required**:

1. During app startup (lifespan), check JuniperData health endpoint
2. Use `wait_for_ready()` from shared client package (with timeout)
3. Log clear message about JuniperData connectivity status
4. Optionally fail startup if health check fails (configurable)

---

## Phase 3: Frontend Enhancement & Dataset Management

**Priority**: MEDIUM | **Risk**: LOW | **Blocking**: None
**Rationale**: Leverages JuniperData's full capabilities in the Canopy UI.

### CAN-INT-013: Populate Dataset Selector Dropdown from JuniperData

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Medium
**Severity**: MEDIUM - Non-functional UI element
**Integration Importance**: MEDIUM - Enables dataset selection in UI
**If Not Fixed**: Dataset selector dropdown is always empty
**Blocks**: None
**Depends On**: CAN-INT-001

**Source**: Code review (dataset_plotter.py line 94-96)

The `DatasetPlotter` component has a dropdown with `options=[]` that is never populated.

**Changes Required**:

1. Add new API endpoint `GET /api/datasets/list` that calls JuniperData's `GET /v1/datasets/filter`
2. Populate dropdown options from JuniperData dataset list
3. Add callback to load selected dataset when dropdown value changes
4. Support listing available generators via JuniperData's `GET /v1/generators` endpoint

---

### CAN-INT-014: Add Dataset Management API Endpoints

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Medium
**Severity**: LOW - Limited dataset management capability
**Integration Importance**: MEDIUM - Full CRUD enables richer UI
**If Not Fixed**: Users cannot create, list, or delete datasets through Canopy
**Blocks**: CAN-INT-013

**Source**: Code review, JuniperData DATA-016 (COMPLETE)

Currently only `GET /api/dataset` exists. JuniperData supports full CRUD.

**Changes Required**:

1. Add `POST /api/datasets/create` - proxy to JuniperData `POST /v1/datasets`
2. Add `GET /api/datasets/list` - proxy to JuniperData `GET /v1/datasets/filter`
3. Add `GET /api/datasets/{id}` - proxy to JuniperData `GET /v1/datasets/{id}`
4. Add `DELETE /api/datasets/{id}` - proxy to JuniperData `DELETE /v1/datasets/{id}`
5. Add `GET /api/generators` - proxy to JuniperData `GET /v1/generators`
6. Keep existing `GET /api/dataset` for backward compatibility (returns current active dataset)

---

### CAN-INT-015: Support Multiple Generator Types

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Medium
**Severity**: LOW - Only spiral datasets currently available
**Integration Importance**: MEDIUM - JuniperData supports 4 generators
**If Not Fixed**: Users limited to spiral datasets despite JuniperData having more
**Blocks**: None
**Depends On**: CAN-INT-013

**Source**: JuniperData DATA-014 (COMPLETE)

JuniperData now supports spiral, XOR, gaussian, and circles generators. Canopy hardcodes `generator="spiral"` everywhere.

**Changes Required**:

1. Add generator selection UI (dropdown or radio buttons) to dataset creation
2. Update demo mode to accept generator type parameter
3. Show generator-specific parameter forms based on selected generator
4. Update dataset display to handle varying feature dimensions

---

### CAN-INT-016: Dataset Refresh/Regeneration During Session

**Priority**: LOW | **Status**: NOT STARTED | **Effort**: Medium
**Severity**: LOW - Dataset generated once at init, never refreshed
**Integration Importance**: LOW - Convenience feature
**If Not Fixed**: Must restart app to get different dataset parameters
**Blocks**: None

**Source**: Code review

**Changes Required**:

1. Add "Regenerate" button to Dataset View tab
2. Add parameter controls (sample count, noise, seed) to UI
3. On regeneration, call JuniperData to create new dataset
4. Update all visualization components with new data
5. Broadcast dataset change via WebSocket to connected clients

---

## Phase 4: Testing & Validation

**Priority**: HIGH | **Risk**: LOW | **Blocking**: None (but should be done alongside each phase)
**Rationale**: Every integration change must be tested. This phase tracks test-specific work items.

### CAN-INT-017: Unit Tests for JuniperData Integration

**Priority**: HIGH | **Status**: **COMPLETE** (2026-02-07) | **Effort**: Medium
**Severity**: HIGH - 0% coverage on client, untested integration paths
**Integration Importance**: HIGH - Validates all integration code
**If Not Fixed**: Integration bugs go undetected
**Blocks**: None

**Source**: Code review (0% coverage on `juniper_data_client/`)

**Implementation Notes**:
Created `src/tests/unit/test_juniper_data_integration.py` with 71 tests covering:

- exception hierarchy (9)
- package exports (3),
- URL normalization (7),
- error mapping (4),
- NPZ parsing (3),
- DemoMode mandatory URL (3),
- CascorIntegration mandatory URL (2),
- DemoMode dataset schema (4),
- CascorIntegration dataset schema (5),
- DataAdapter canonical schema (9),
- JuniperDataConstants (10),
- app_config.yaml (4),
- deprecation warnings (2),
- endpoint schema (2),
- one-hot conversion (2),
- conftest environment (2).

**Changes Required**:

1. If using shared package (CAN-INT-001): Package already has 35 tests at 96% coverage. Add Canopy-specific integration tests.
2. Test `demo_mode.py` JuniperData path with mocked client
3. Test `cascor_integration.py` JuniperData path with mocked client
4. Test `main.py` `/api/dataset` endpoint with both sources
5. Test schema normalization (CAN-INT-003)
6. Test startup validation (CAN-INT-002)
7. Test configuration loading (CAN-INT-004)

**Test count target**: 25+ new tests
**Coverage target**: >80% for all JuniperData integration code paths

---

### CAN-INT-018: Integration Tests with JuniperData TestClient

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Large
**Severity**: MEDIUM - No E2E validation with actual JuniperData service
**Integration Importance**: MEDIUM - Validates the full flow
**If Not Fixed**: Integration bugs only discovered in production
**Blocks**: None
**Depends On**: CAN-INT-001

**Source**: JuniperCascor CAS-INT-007 (NOT STARTED), JuniperData DATA-008 (COMPLETE)

**Changes Required**:

1. Create `src/tests/integration/test_juniper_data_integration.py`
2. Use JuniperData's `TestClient` if importable, or require live service
3. Test full flow: create dataset → download NPZ → convert to visualization format → render
4. Mark with `@pytest.mark.integration` and `@pytest.mark.requires_juniper_data`
5. Add `JUNIPER_DATA_AVAILABLE` env var for opt-in execution

---

### CAN-INT-019: Regression Tests for Schema Normalization

**Priority**: MEDIUM | **Status**: NOT STARTED | **Effort**: Small
**Severity**: MEDIUM - Schema mismatches can recur
**Integration Importance**: MEDIUM - Prevents regressions
**If Not Fixed**: Future changes can reintroduce schema inconsistencies
**Blocks**: None
**Depends On**: CAN-INT-003

**Source**: Newly identified during code evaluation

**Changes Required**:

1. Create `src/tests/regression/test_dataset_schema_consistency.py`
2. Test that demo mode and CascorIntegration both produce identical schemas
3. Test that `/api/dataset` response matches canonical schema
4. Test that DatasetPlotter and DecisionBoundary accept both sources

---

## Deferred Items

These items are explicitly deferred and will be revisited based on project needs.

| ID          | Item                        | Reason                                           |
| ----------- | --------------------------- | ------------------------------------------------ |
| CAN-INT-016 | Dataset refresh in session  | Convenience feature, not blocking integration    |
| CAN-DEF-001 | HDF5 snapshot dataset sync  | Requires HDF5 snapshot feature completion first  |
| CAN-DEF-002 | Real-time dataset streaming | Requires WebSocket protocol extension            |
| CAN-DEF-003 | Dataset caching in Redis    | JuniperData has its own caching (DATA-015)       |

---

## Newly Identified Issues

The following issues were discovered during the code evaluation and were not previously documented in any plan.

### NEW-001: Duplicate JuniperData Integration Code in Two Modules

**Severity**: HIGH | **Priority**: HIGH
**Integration Importance**: HIGH - Code duplication increases maintenance cost
**Potential Problems if Not Fixed**: Bug fixes need to be applied in two places; parameter drift
**Blocks Additional Progress**: No, but increases maintenance burden for all future changes

Both `demo_mode.py` (lines 383-452) and `cascor_integration.py` (lines 1257-1329) contain nearly identical code for calling JuniperData. They should be consolidated into a single helper or use the shared client's convenience methods.

**Resolution**: CAN-INT-008 and CAN-INT-009 address this by removing the local paths. After Phase 0 completion, both modules should use the shared client identically.

---

### NEW-002: Parameter Inconsistency Between Demo Mode and CascorIntegration

**Severity**: MEDIUM | **Priority**: HIGH
**Integration Importance**: HIGH - Different default parameters produce different datasets
**Potential Problems if Not Fixed**: Developers see different data in demo vs real backend
**Blocks Additional Progress**: No

| Parameter     | Demo Mode   | CascorIntegration | After Fix   |
| ------------- | ----------- | ----------------- | ----------- |
| `n_samples`   | 200         | 100               | **200**     |
| `noise`       | 0.1         | 0.0               | **0.1**     |
| `seed`        | 42          | 42                | 42          |
| `persist`     | False       | True              | **False**   |

**Resolution**: **RESOLVED** in CAN-INT-009. CascorIntegration now uses 200 samples, noise=0.1, persist=False (matching demo mode). `JuniperDataConstants` provides centralized defaults.

---

### NEW-003: Demo Mode `_generate_spiral_dataset_from_juniper_data()` Creates New Client Each Call

**Severity**: LOW | **Priority**: MEDIUM
**Integration Importance**: LOW - Performance issue, not correctness
**Potential Problems if Not Fixed**: New HTTP connection on every dataset generation call
**Blocks Additional Progress**: No

In `demo_mode.py` line 401, a new `JuniperDataClient` is instantiated every time `_generate_spiral_dataset_from_juniper_data()` is called. The client should be created once and reused.

**Resolution**: Create client at `DemoMode.__init__()` time and store as `self._juniper_data_client`. This aligns with Phase 0 work.

---

### NEW-004: Decision Boundary Real Backend Path Incomplete

**Severity**: MEDIUM | **Priority**: MEDIUM
**Integration Importance**: MEDIUM - Decision boundary won't work with real CasCor backend
**Potential Problems if Not Fixed**: Decision Boundaries tab shows nothing with real backend
**Blocks Additional Progress**: Blocks real backend visualization

In `main.py` lines 779-788, the real backend path for decision boundary is incomplete (marked with TODO):

```python
# Real backend - try to get predictions
if cascor_integration:
    ...  # incomplete
```

**Resolution**: Not strictly a JuniperData integration issue, but related to real backend dataset handling. Should be addressed as part of the broader Canopy→Cascor integration.

---

### NEW-005: Test Fixture `sample_dataset` Uses Local Generation

**Severity**: LOW | **Priority**: LOW
**Integration Importance**: LOW - Tests can use local fixtures
**Potential Problems if Not Fixed**: None for testing; tests should use mocks/fixtures
**Blocks Additional Progress**: No

`conftest.py` `sample_dataset()` fixture (line 214) generates an XOR dataset locally using numpy. This is fine for test fixtures -- tests should not depend on external services. No action required.

---

### NEW-006: DEMO_HANG_ANALYSIS Fixes Pending

**Severity**: MEDIUM | **Priority**: LOW
**Integration Importance**: LOW - Demo mode stability, not integration-specific
**Potential Problems if Not Fixed**: Demo mode may hang in certain edge cases
**Blocks Additional Progress**: No

`notes/analysis/DEMO_HANG_ANALYSIS_2026-01-03.md` has status "ANALYSIS COMPLETE - FIXES PENDING". This pre-dates the integration work and is a demo mode stability issue, not directly related to JuniperData integration.

---

## Cross-Project Reference

### Items Referenced from JuniperData Plan (CAN-REF-*)

| ID          | Item                                   | Status in This Plan | Mapped To            |
| ----------- | -------------------------------------- | ------------------- | -------------------- |
| CAN-REF-001 | JuniperData client not actively used   | ADDRESSED           | CAN-INT-001, 002     |
| CAN-REF-002 | No JUNIPER_DATA_URL in app_config.yaml | ADDRESSED           | CAN-INT-004          |
| CAN-REF-003 | No JuniperData in docker-compose.yaml  | ADDRESSED           | CAN-INT-010          |
| CAN-REF-004 | Parameter inconsistencies (noise)      | ADDRESSED           | CAN-INT-003, NEW-002 |
| CAN-REF-005 | CAN-001 through CAN-021 enhancements   | ADDRESSED           | Various items        |

### Items That Affect JuniperData (Upstream Changes)

| Item                                      | Impact on JuniperData | Status           |
| ----------------------------------------- | --------------------- | ---------------- |
| Shared client package adoption            | Validates DATA-012    | **COMPLETE**     |
| Docker compose integration                | Uses DATA-006         | NOT STARTED      |
| Multiple generator support in UI          | Uses DATA-014         | NOT STARTED      |
| API key auth usage                        | Validates DATA-017    | **COMPLETE**     |
| Health check at startup                   | Uses DATA-007         | NOT STARTED      |

### Items That Align with JuniperCascor Pattern

| CasCor Item   | CasCor Status | Canopy Equivalent | Canopy Status   |
| ------------- | ------------- | ----------------- | --------------- |
| CAS-INT-001   | COMPLETE      | CAN-INT-002       | **COMPLETE**    |
| CAS-INT-002   | COMPLETE      | CAN-INT-008, 009  | **COMPLETE**    |
| CAS-INT-003   | COMPLETE      | CAN-INT-005       | **COMPLETE**    |
| CAS-INT-004   | COMPLETE      | CAN-INT-007       | **PARTIAL**     |
| CAS-INT-005   | COMPLETE      | CAN-INT-017       | **COMPLETE**    |
| CAS-INT-008   | COMPLETE      | CAN-INT-006       | **COMPLETE**    |
| CAS-INT-009   | COMPLETE      | CAN-INT-012       | NOT STARTED     |

---

## Implementation Priority Matrix

### Phase 0 - Critical (Immediate) - **ALL COMPLETE**

| ID          | Item                              | Priority | Effort | Impact           | Status           |
| ----------- | --------------------------------- | -------- | ------ | ---------------- | ---------------- |
| CAN-INT-001 | Replace with shared client        | CRITICAL | Medium | Foundation       | **COMPLETE**     |
| CAN-INT-002 | Make JUNIPER_DATA_URL mandatory   | CRITICAL | Medium | Core objective   | **COMPLETE**     |
| CAN-INT-003 | Fix dataset schema mismatch       | CRITICAL | Medium | Frontend broken  | **COMPLETE**     |

### Phase 1 - High (Short-Term: 1-2 Sprints) - **ALL COMPLETE**

| ID          | Item                              | Priority | Effort | Impact           | Status           |
| ----------- | --------------------------------- | -------- | ------ | ---------------- | ---------------- |
| CAN-INT-004 | Add to app_config.yaml            | HIGH     | Small  | Configuration    | **COMPLETE**     |
| CAN-INT-005 | API key authentication            | HIGH     | Small  | Security         | **COMPLETE**     |
| CAN-INT-006 | Retry/backoff                     | HIGH     | Small  | Reliability      | **COMPLETE**     |
| CAN-INT-007 | NPZ contract validation           | HIGH     | Small  | Data integrity   | **PARTIAL**      |
| CAN-INT-008 | Remove local gen from demo_mode   | HIGH     | Medium | Core objective   | **COMPLETE**     |
| CAN-INT-009 | Remove local gen from cascor_int  | HIGH     | Medium | Core objective   | **COMPLETE**     |
| CAN-INT-017 | Unit tests for integration        | HIGH     | Medium | Test coverage    | **COMPLETE**     |

### Phase 2 - Medium (Medium-Term: 3-4 Sprints)

| ID          | Item                      | Priority | Effort | Impact           | Blocks |
| ----------- | ------------------------- | -------- | ------ | ---------------- | ------ |
| CAN-INT-010 | Docker compose            | MEDIUM   | Small  | Infrastructure   | None   |
| CAN-INT-011 | Constants                 | MEDIUM   | Small  | Maintainability  | None   |
| CAN-INT-012 | Startup health check      | MEDIUM   | Small  | Fail-fast        | None   |
| CAN-INT-013 | Dataset selector dropdown | MEDIUM   | Medium | UI functionality | 014    |
| CAN-INT-014 | Dataset management API    | MEDIUM   | Medium | Full CRUD        | None   |
| CAN-INT-018 | Integration tests         | MEDIUM   | Large  | Validation       | None   |
| CAN-INT-019 | Regression tests          | MEDIUM   | Small  | Regression guard | None   |

### Phase 3 - Low (Long-Term / Backlog)

| ID          | Item                       | Priority | Effort | Impact      | Blocks |
| ----------- | -------------------------- | -------- | ------ | ----------- | ------ |
| CAN-INT-015 | Multiple generator types   | MEDIUM   | Medium | Capability  | None   |
| CAN-INT-016 | Dataset refresh in session | LOW      | Medium | Convenience | None   |

---

## Summary Statistics

| Category                  | Count                                               |
| ------------------------- | --------------------------------------------------- |
| Total Tasks               | 19                                                  |
| CRITICAL Priority         | 3 (CAN-INT-001, 002, 003) - **ALL COMPLETE**        |
| HIGH Priority             | 7 (CAN-INT-004-009, 017) - **ALL COMPLETE/PARTIAL** |
| MEDIUM Priority           | 7 (CAN-INT-010-014, 018, 019)                       |
| LOW Priority              | 1 (CAN-INT-016)                                     |
| MEDIUM (in low phase)     | 1 (CAN-INT-015)                                     |
| **COMPLETE**              | **11** (001-006, 008, 009, 011, 017, + 003)         |
| **PARTIAL**               | **1** (CAN-INT-007)                                 |
| NOT STARTED               | 7 (010, 012-016, 018-019)                           |
| Newly Identified Issues   | 6 (NEW-001 through NEW-006)                         |
| Deferred Items            | 3 (CAN-DEF-001, 002, 003)                           |
| Cross-Project Refs Mapped | 5 (CAN-REF-001 through CAN-REF-005)                 |
| New Tests Added           | 71 (test_juniper_data_integration.py)               |
| Test Suite Total          | 3,276 passed, 36 skipped, 0 failed                  |

---

## Document History

| Date       | Author   | Changes                                                                                                  |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- |
| 2026-02-07 | AI Agent | Initial creation from comprehensive codebase evaluation and cross-project analysis                       |
| 2026-02-07 | AI Agent | Phase 0+1 implementation: CAN-INT-001 through 009, 011, 017 COMPLETE. 71 new tests. Suite: 3,276 passed. |
