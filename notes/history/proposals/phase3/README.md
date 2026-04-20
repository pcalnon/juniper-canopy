# Phase 3: Advanced Features

**Last Updated:** 2026-01-10  
**Version:** 1.5.0  
**Status:** ✅ COMPLETE (All P3-1 through P3-7 Done, All Waves Complete, Testing Verified)

## Overview

Phase 3 builds on the completed Phase 0, Phase 1, and Phase 2 implementations with advanced features and infrastructure integrations. These P3 items include new snapshot operations, visualization enhancements, and external service monitoring capabilities.

**Estimated Effort:** Multi-week  
**Target Coverage After Phase 3:** 95%+

---

## Table of Contents

- [Implementation Order](#implementation-order)
- [Wave 1: HDF5 Snapshot Capabilities](#wave-1-hdf5-snapshot-capabilities)
  - [P3-1: HDF5 Tab - Create New Snapshot](#p3-1-hdf5-tab---create-new-snapshot)
  - [P3-2: HDF5 Tab - Restore from Existing Snapshot](#p3-2-hdf5-tab---restore-from-existing-snapshot)
  - [P3-3: HDF5 Tab - Show History of Snapshot Activities](#p3-3-hdf5-tab---show-history-of-snapshot-activities)
- [Wave 2: UX & Visualization Enhancements](#wave-2-ux--visualization-enhancements)
  - [P3-4: Training Metrics Tab - Save/Load Buttons](#p3-4-training-metrics-tab---saveload-buttons)
  - [P3-5: Network Topology Tab - 3D Interactive View](#p3-5-network-topology-tab---3d-interactive-view)
- [Wave 3: Infrastructure Integrations](#wave-3-infrastructure-integrations)
  - [P3-6: Redis Integration and Monitoring Tab](#p3-6-redis-integration-and-monitoring-tab)
  - [P3-7: Cassandra Integration and Monitoring Tab](#p3-7-cassandra-integration-and-monitoring-tab)
- [Implementation Summary](#implementation-summary)
- [Verification Checklist](#verification-checklist)

---

## Implementation Order

Phase 3 is organized into three waves based on dependencies, complexity, and coverage impact:

### Wave 1: HDF5 Snapshot Capabilities (Core, High Leverage)

1. **P3-1: Create new snapshot** - Effort: M (1-3h)
2. **P3-2: Restore from existing snapshot** - Effort: L (1-2d)
3. **P3-3: Show history of snapshot activities** - Effort: S-M (<3h)

**Rationale:**

- Targets lowest-coverage frontend file (`hdf5_snapshots_panel.py` at 48%)
- Builds on existing infrastructure (P2-4, P2-5)
- Natural dependency chain: Create → Restore → History
- Solidifies training state serialization and recovery

### Wave 2: UX & Visualization Enhancements (Medium Leverage)

1. **P3-4: Metrics Save/Load buttons** - Effort: M (1-3h)
2. **P3-5: 3D interactive topology view** - Effort: L (1-2d)

**Rationale:**

- Frontend-heavy, relies on stable existing infrastructure
- Provides visible user value quickly
- Improves coverage in `dashboard_manager.py`, `metrics_panel.py`

### Wave 3: Infrastructure Integrations (Low Leverage)

1. **P3-6: Redis Integration Tab** - Effort: L (1-2d)
2. **P3-7: Cassandra Integration Tab** - Effort: XL (>2d)

**Rationale:**

- Introduces new infrastructure and failure modes
- Redis first provides reusable patterns for Cassandra
- Best tackled after core training/snapshot flows are stable

---

## Wave 1: HDF5 Snapshot Capabilities

### P3-1: HDF5 Tab - Create New Snapshot

#### Problem, P3-1

Users need the ability to create new HDF5 snapshots of the current training state. Currently, the HDF5 Snapshots tab only supports viewing and listing existing snapshots.

#### Current State, P3-1

From Phase 2 (P2-4, P2-5):

- Backend has `/api/v1/snapshots` endpoint for listing snapshots
- Backend has `/api/v1/snapshots/{snapshot_id}` for details
- Frontend has `HDF5SnapshotsPanel` with table view and detail panel
- Helpers exist: `_list_snapshot_files()`, `_generate_mock_snapshots()`
- No create functionality exists

#### Solution Design, P3-1

**Files to Modify:**

1. **`src/main.py`**:
   - Add `POST /api/v1/snapshots` endpoint
   - Add `_create_snapshot()` helper for real backend
   - Add `_create_mock_snapshot()` helper for demo mode
   - Log snapshot creation for history tracking

2. **`src/frontend/components/hdf5_snapshots_panel.py`**:
   - Add "Create Snapshot" button to layout (near Refresh button)
   - Add name input field (optional, auto-generated default)
   - Add callback for create button click
   - Add `_create_snapshot_handler()` to POST to backend
   - Show success/error status message
   - Auto-refresh table after successful creation

**API Contract:**

```http
POST /api/v1/snapshots
Content-Type: application/json

{
  "name": "optional_custom_name",
  "description": "Optional description"
}

Response (201 Created):
{
  "id": "snapshot_20260108_143022",
  "name": "snapshot_20260108_143022.h5",
  "timestamp": "2026-01-08T14:30:22Z",
  "size_bytes": 1048576,
  "path": "/path/to/snapshots/snapshot_20260108_143022.h5",
  "message": "Snapshot created successfully"
}

Response (500 Error):
{
  "error": "Failed to create snapshot",
  "detail": "Specific error message"
}
```

#### Tests Required, P3-1

**Backend Tests:**

- Test create endpoint returns 201 on success
- Test create endpoint with custom name
- Test create endpoint in demo mode
- Test create endpoint failure handling
- Test snapshot file is created in correct directory

**Frontend Tests:**

- Test create button appears in layout
- Test create callback triggers POST request
- Test success message displayed
- Test error message displayed on failure
- Test table refreshes after creation

#### Implementation Notes, P3-1

- Snapshot names should be auto-generated with timestamp if not provided
- Demo mode should create mock entries that persist for the session
- Real mode should serialize current training state via `cascor_integration`
- Log all create operations for history feature (P3-3)

#### Solution Implemented, P3-1

**Files Modified:**

1. **`src/main.py`** (lines 975-1152):
   - Added `_demo_snapshots` list for session-persistent demo snapshots
   - Added `_log_snapshot_activity()` helper for history logging (P3-3 preparation)
   - Added `POST /api/v1/snapshots` endpoint with:
     - Demo mode: creates mock snapshot entries in `_demo_snapshots`
     - Real mode: creates HDF5 file via h5py or `cascor_integration.save_snapshot()`
   - Updated `get_snapshots()` to return session-created demo snapshots
   - Updated `get_snapshot_detail()` to handle session-created snapshots

2. **`src/frontend/components/hdf5_snapshots_panel.py`**:
   - Added `DEFAULT_API_BASE_URL` constant (line 51)
   - Added Create Snapshot section with:
     - Name input field (optional, auto-generated if empty)
     - Description input field (optional)
     - "📸 Create Snapshot" button
     - Status message area for success/error feedback
   - Added `refresh-trigger` Store for table refresh after creation
   - Added `_create_snapshot_handler()` method (lines 275-319)
   - Added `create_snapshot` callback for button click handling

#### Tests Added, P3-1

**Unit Tests (13 new tests):**

- `TestHDF5SnapshotsCreateHandler` (7 tests): Handler success/failure/timeout/error
- `TestHDF5SnapshotsCreateLayout` (6 tests): Layout elements verification

**Integration Tests (10 new tests):**

- `TestCreateSnapshotEndpoint`: API endpoint tests for POST /api/v1/snapshots

#### Verification, P3-1

- [x] Create button appears in HDF5 Snapshots panel
- [x] Name input allows custom snapshot names
- [x] Default name uses timestamp format (`snapshot_YYYYMMDD_HHMMSS`)
- [x] POST endpoint creates snapshot successfully (201 response)
- [x] Demo mode creates mock snapshots
- [x] Success message displayed after creation
- [x] Table refreshes to show new snapshot
- [x] Error handling for creation failures
- [x] Created snapshots appear in list endpoint
- [x] Created snapshots accessible via detail endpoint

#### Status, P3-1

**Status:** ✅ COMPLETE

---

### P3-2: HDF5 Tab - Restore from Existing Snapshot

#### Problem, P3-2

Users need to restore training state from a previously saved HDF5 snapshot. Currently, snapshots can only be viewed but not loaded.

#### Current State, P3-2

- Snapshot listing and details work (P2-4, P2-5)
- No restore functionality exists
- Training state management exists in `training_state_machine.py`
- WebSocket broadcasting exists for state updates

#### Solution Design, P3-2

**Files to Modify:**

1. **`src/main.py`**:
   - Add `POST /api/v1/snapshots/{snapshot_id}/restore` endpoint
   - Add `_restore_snapshot()` helper for real backend
   - Add `_restore_mock_snapshot()` helper for demo mode
   - Validate training state before restore (must be paused/stopped)
   - Broadcast state change via WebSocket after restore

2. **`src/frontend/components/hdf5_snapshots_panel.py`**:
   - Add "Restore" button to each table row (next to "View Details")
   - Add confirmation dialog before restore
   - Add callback for restore button click
   - Add `_restore_snapshot_handler(snapshot_id)` to POST to backend
   - Show success/error status message

3. **`src/backend/training_state_machine.py`** (if needed):
   - Add `restore_from_snapshot()` method
   - Handle state transitions during restore

4. **`src/communication/websocket_manager.py`** (if needed):
   - Broadcast state update after restore

**API Contract:**

```http
POST /api/v1/snapshots/{snapshot_id}/restore

Response (200 OK):
{
  "id": "snapshot_001",
  "message": "Snapshot restored successfully",
  "restored_state": {
    "epoch": 150,
    "hidden_units": 4,
    "phase": "training"
  }
}

Response (400 Bad Request):
{
  "error": "Cannot restore while training is running",
  "detail": "Stop or pause training before restoring"
}

Response (404 Not Found):
{
  "error": "Snapshot not found",
  "detail": "No snapshot with ID: snapshot_xyz"
}
```

#### Tests Required, P3-2

**Backend Tests:**

- Test restore endpoint returns 200 on success
- Test restore endpoint validates training state
- Test restore endpoint with invalid snapshot ID
- Test restore in demo mode
- Test WebSocket broadcast after restore

**Frontend Tests:**

- Test restore button appears in each row
- Test restore callback triggers POST request
- Test confirmation dialog appears
- Test success/error messages displayed

#### Implementation Notes, P3-2

- Only allow restore when training is paused or stopped
- Validate snapshot file exists before attempting restore
- Update all training-related stores after restore
- Broadcast state change so all UI components update

#### Status, P3-2

**Status:** ✅ COMPLETE

---

### P3-3: HDF5 Tab - Show History of Snapshot Activities

#### Problem, P3-3

Users need visibility into the history of snapshot operations (create, restore, delete) for audit and troubleshooting purposes.

#### Current State, P3-3

- No history tracking exists
- Snapshot operations are not logged

#### Solution Design, P3-3

**Files to Create:**

1. **Snapshot History Log** (`_snapshots_dir/snapshot_history.jsonl`):
   - Append-only JSONL format
   - Each entry: `{timestamp, action, snapshot_id, details, message}`

**Files to Modify:**

1. **`src/main.py`**:
   - Add `GET /api/v1/snapshots/history` endpoint
   - Add `_log_snapshot_activity()` helper
   - Add `_read_snapshot_history()` helper
   - Call logging from create/restore endpoints

2. **`src/frontend/components/hdf5_snapshots_panel.py`**:
   - Add collapsible "History" section below detail panel
   - Add callback to fetch and display history
   - Show entries in reverse chronological order
   - Include action type, timestamp, snapshot ID, and details

**API Contract:**

```http
GET /api/v1/snapshots/history?limit=50

Response (200 OK):
{
  "history": [
    {
      "timestamp": "2026-01-08T14:30:22Z",
      "action": "create",
      "snapshot_id": "snapshot_001",
      "details": {"name": "snapshot_001.h5", "size_bytes": 1048576},
      "message": "Snapshot created successfully"
    },
    {
      "timestamp": "2026-01-08T14:25:00Z",
      "action": "restore",
      "snapshot_id": "snapshot_002",
      "details": {"epoch": 100, "hidden_units": 3},
      "message": "Snapshot restored successfully"
    }
  ],
  "total": 15
}
```

#### Tests Required, P3-3

**Backend Tests:**

- Test history endpoint returns entries
- Test history logging on create
- Test history logging on restore
- Test history pagination/limit
- Test empty history handling

**Frontend Tests:**

- Test history section appears in layout
- Test history entries display correctly
- Test empty state message

#### Implementation Notes, P3-3

- Use simple JSONL file for low-ceremony persistence
- Limit history to last N entries (configurable)
- In demo mode, maintain in-memory history

#### Status, P3-3

**Status:** ✅ COMPLETE

---

## Wave 2: UX & Visualization Enhancements

### P3-4: Training Metrics Tab - Save/Load Buttons

#### Problem, P3-4

Users need to save and load training metric layouts/configurations and potentially training state for later analysis or continuation.

#### Current State, P3-4

- MetricsPanel exists with training metrics display
- Training controls exist for hyperparameters
- No save/load functionality for layouts or state

#### Solution Design, P3-4

**Scope (Minimal Viable):**

- Save/load metric panel configuration (selected metrics, zoom ranges, smoothing)
- Save/load associated training hyperparameters as named presets

**Files to Create:**

1. **`src/backend/metrics_presets.py`** (optional, if logic is complex):
   - Preset storage and retrieval logic

**Files to Modify:**

1. **`src/main.py`**:
   - Add `GET /api/v1/metrics/layouts` endpoint
   - Add `POST /api/v1/metrics/layouts` endpoint
   - Add `GET /api/v1/metrics/layouts/{name}` endpoint
   - Store presets in JSON file in config directory

2. **`src/frontend/components/metrics_panel.py`**:
   - Add "Save Layout" button with name input
   - Add "Load Layout" dropdown/button
   - Add callbacks for save/load operations

#### Tests Required, P3-4

- Test save endpoint creates preset
- Test load endpoint returns preset
- Test list endpoint returns all presets
- Test UI buttons trigger correct API calls

#### Solution Implemented, P3-4

**Files Modified:**

1. **`src/main.py`** (lines 1405-1591):
   - Added `_layouts_dir` path for layout storage
   - Added `_get_layouts_file()`, `_load_layouts()`, `_save_layouts()` helpers
   - Added `GET /api/v1/metrics/layouts` endpoint to list all layouts
   - Added `GET /api/v1/metrics/layouts/{name}` to get a specific layout
   - Added `POST /api/v1/metrics/layouts` to save a layout
   - Added `DELETE /api/v1/metrics/layouts/{name}` to delete a layout

2. **`src/frontend/components/metrics_panel.py`** (v1.5.0):
   - Added Layout Controls section with:
     - Name input field for saving layouts
     - "💾 Save" button to save current layout
     - Dropdown to select saved layouts
     - "📂 Load" button to apply selected layout
     - "🗑️" delete button to remove layouts
     - Status message area for feedback
   - Added `dcc.Store` for layout data refresh triggers
   - Added callbacks for save/load/delete operations
   - Added handler methods:
     - `_fetch_layout_options_handler()` - fetch dropdown options
     - `_save_layout_handler()` - save layout to API
     - `_load_layout_handler()` - load layout from API
     - `_delete_layout_handler()` - delete layout via API

#### Tests Added, P3-4

**Unit Tests (24 new tests in `test_metrics_panel_layouts.py`):**

- `TestFetchLayoutOptionsHandler` (4 tests): API success/empty/error/network
- `TestSaveLayoutHandler` (7 tests): No clicks, empty name, success, errors
- `TestLoadLayoutHandler` (5 tests): No clicks, no selection, success, not found, timeout
- `TestDeleteLayoutHandler` (5 tests): No clicks, no selection, success, not found, timeout
- `TestLayoutControlsLayout` (3 tests): UI elements present

**Integration Tests (13 new tests in `test_metrics_layouts_api.py`):**

- `TestListMetricsLayouts`: Empty list, with data
- `TestGetMetricsLayout`: Not found, success
- `TestSaveMetricsLayout`: Success, with params, empty name, overwrites
- `TestDeleteMetricsLayout`: Not found, success
- `TestLayoutPersistence`: File persistence, deletion

#### Verification, P3-4

- [x] Save button appears in metrics panel
- [x] Name input allows custom layout names
- [x] POST endpoint creates layout successfully (201 response)
- [x] Layouts persist to conf/layouts/metrics_layouts.json
- [x] Load dropdown shows available layouts
- [x] Load button applies selected layout
- [x] Delete button removes layout
- [x] Success/error messages displayed
- [x] All 37 new tests pass

#### Status, P3-4

**Status:** ✅ COMPLETE

---

### P3-5: Network Topology Tab - 3D Interactive View

#### Problem, P3-5

Users need an interactive 3D visualization of the network topology for better understanding of complex network structures.

#### Current State, P3-5

- NetworkVisualizer provides 2D view
- `get_network_topology()` returns node and connection data
- No 3D visualization exists

#### Solution Design, P3-5

**Approach:**

- Use Plotly 3D scatter + lines (minimal new dependencies)
- Generate (x, y, z) positions per node using layer as one axis
- Toggle between 2D and 3D view

**Files to Modify:**

1. **`src/frontend/components/network_visualizer.py`**:
   - Add 3D layout generation
   - Add Scatter3d traces for nodes and connections
   - Add 2D/3D toggle button
   - Maintain interaction features (rotate, zoom, hover)

#### Tests Required, P3-5

- Test 3D layout generation
- Test toggle between 2D and 3D
- Test 3D interactions work
- Test 2D mode still works after adding 3D

#### Solution Implemented, P3-5

**Files Modified:**

1. **`src/frontend/components/network_visualizer.py`** (v1.7.0):
   - Added 2D/3D view mode radio toggle in header controls
   - Added `view_mode` input to main callback
   - Added `_create_3d_network_graph()` method:
     - Creates Scatter3d traces for nodes by layer
     - Creates 3D edge traces with weight-based coloring
     - Sets up 3D scene with camera, aspect ratio, and grid
     - Supports light and dark themes
   - Added `_calculate_3d_layout()` method:
     - Places input nodes at z=0, hidden at z=1, output at z=2
     - Uses linear arrangement for ≤4 hidden nodes
     - Uses circular arrangement for >4 hidden nodes
   - Updated `_create_empty_graph()` to support view_mode parameter

**3D Visualization Features:**

- Layer-based z-axis (Input → Hidden → Output)
- Color-coded nodes by layer (Green/Teal/Red)
- Weight-based edge coloring (Blue negative, Red positive)
- Interactive camera rotation, zoom, and pan
- Grid lines on each axis for spatial reference
- Dark/light theme support

#### Tests Added, P3-5

**Unit Tests (19 new tests in `test_network_visualizer_3d.py`):**

- `TestViewModeToggle` (2 tests): Toggle in layout, default is 2D
- `TestCalculate3DLayout` (6 tests): Returns dict, input/hidden/output z-positions, no hidden, circular
- `TestCreate3DNetworkGraph` (6 tests): Returns figure, Scatter3d traces, edges, nodes by layer, dark theme, camera
- `TestCreateEmptyGraph3D` (3 tests): 2D default, 3D mode, dark theme
- `TestEdgeWeightColoring` (2 tests): Positive/negative weights

#### Verification, P3-5

- [x] 2D/3D toggle radio buttons appear in Network Topology panel
- [x] Default view is 2D (existing functionality preserved)
- [x] Selecting 3D renders Scatter3d traces
- [x] Nodes positioned by layer on z-axis
- [x] Hidden nodes use circular layout when >4 nodes
- [x] Edges colored by weight (blue negative, red positive)
- [x] 3D scene supports rotate/zoom/pan
- [x] Dark theme applies correctly
- [x] All 19 new tests pass
- [x] Existing 2D tests still pass (4 callback tests updated)

#### Status, P3-5

**Status:** ✅ COMPLETE

---

## Wave 3: Infrastructure Integrations

### P3-6: Redis Integration and Monitoring Tab

#### Problem, P3-6

Users need visibility into Redis cluster state and usage statistics for the Juniper Cascor backend.

#### Current State, P3-6

- No Redis integration exists
- WebSocket and statistics infrastructure exists

#### Solution Design, P3-6

**Files to Create:**

1. **`src/backend/redis_client.py`**:
   - Redis client wrapper
   - Health check methods
   - Metrics collection

2. **`src/frontend/components/redis_panel.py`**:
   - New component following BaseComponent pattern
   - Health summary (UP/DOWN, latency)
   - Key metrics display

**Files to Modify:**

1. **`src/main.py`**:
   - Add `/api/v1/redis/status` endpoint
   - Add `/api/v1/redis/metrics` endpoint

2. **`src/frontend/dashboard_manager.py`**:
   - Import and register RedisPanel
   - Add Redis Monitoring tab

#### Implementation Notes, P3-6

- Make Redis integration strictly optional
- Fail soft with DISABLED/UNAVAILABLE status
- Keep credentials in config/env only

#### Solution Implemented, P3-6

**Files Created:**

1. **`src/backend/redis_client.py`** (v0.1.0):
   - `RedisClient` class with optional redis-py integration
   - `get_status()` returns health with UP/DOWN/DISABLED/UNAVAILABLE
   - `get_metrics()` returns memory, stats, clients, keyspace info
   - Demo mode support with synthetic data
   - Singleton pattern via `get_redis_client()`

2. **`src/frontend/components/redis_panel.py`** (v1.0.0):
   - `RedisPanel` extending `BaseComponent`
   - Auto-refresh via `dcc.Interval` (5s default)
   - Health card: version, uptime, clients, latency
   - Metrics card: memory, ops/sec, hit rate, keyspace
   - Status badge with color-coded status

**Files Modified:**

1. **`src/main.py`**:
   - Added `GET /api/v1/redis/status` endpoint
   - Added `GET /api/v1/redis/metrics` endpoint

2. **`src/frontend/dashboard_manager.py`**:
   - Imported and registered `RedisPanel`
   - Added "Redis" tab to dashboard

#### Tests Added, P3-6

**Unit Tests (97 tests):**

- `test_redis_client.py`: 34 tests for client modes, status, metrics, singleton
- `test_redis_panel.py`: 63 tests for layout, callbacks, formatters, configuration

**Integration Tests (43 tests):**

- `test_redis_endpoints.py`: API endpoint tests, response structure, demo mode

#### Verification, P3-6

- [x] Redis panel appears in dashboard tabs
- [x] Status badge shows UP/DOWN/DISABLED/UNAVAILABLE with colors
- [x] Demo mode returns synthetic metrics
- [x] Health card displays version, uptime, clients, latency
- [x] Metrics card displays memory, ops/sec, hit rate, keyspace
- [x] Auto-refresh via interval component
- [x] Error handling for connection failures
- [x] All 140 tests pass

#### Status, P3-6

**Status:** ✅ COMPLETE

---

### P3-7: Cassandra Integration and Monitoring Tab

#### Problem, P3-7

Users need visibility into Cassandra cluster state and usage statistics for the Juniper Cascor backend.

#### Current State, P3-7

- No Cassandra integration exists
- This is net-new infrastructure

#### Solution Design, P3-7

**Files to Create:**

1. **`src/backend/cassandra_client.py`**:
   - Cassandra client wrapper
   - Connection management
   - Health check methods

2. **`src/frontend/components/cassandra_panel.py`**:
   - New component following BaseComponent pattern
   - Status cards
   - Keyspace/table overview

**Files to Modify:**

1. **`src/main.py`**:
   - Add `/api/v1/cassandra/status` endpoint
   - Add `/api/v1/cassandra/metrics` endpoint

2. **`src/frontend/dashboard_manager.py`**:
   - Import and register CassandraPanel
   - Add Cassandra Monitoring tab

#### Implementation Notes, P3-7

- Make Cassandra integration strictly optional
- Reuse patterns from Redis integration
- Handle security considerations carefully

#### Solution Implemented, P3-7

**Files Created:**

1. **`src/backend/cassandra_client.py`** (v0.1.0):
   - `CassandraClient` class with optional cassandra-driver integration
   - `get_status()` returns cluster health with host information
   - `get_metrics()` returns keyspace/table metrics
   - Demo mode support with synthetic cluster data
   - Singleton pattern via `get_cassandra_client()`

2. **`src/frontend/components/cassandra_panel.py`** (v1.0.0):
   - `CassandraPanel` extending `BaseComponent`
   - Auto-refresh via `dcc.Interval` (10s default)
   - Cluster overview card: contact points, keyspace, hosts table
   - Schema overview card: keyspace count, table count, replication
   - Status badge with color-coded status

**Files Modified:**

1. **`src/main.py`**:
   - Added `GET /api/v1/cassandra/status` endpoint
   - Added `GET /api/v1/cassandra/metrics` endpoint

2. **`src/frontend/dashboard_manager.py`**:
   - Imported and registered `CassandraPanel`
   - Added "Cassandra" tab to dashboard

#### Tests Added, P3-7

**Unit Tests (59 tests):**

- `test_cassandra_client.py`: 24 tests for client modes, status, metrics, singleton
- `test_cassandra_panel.py`: 35 tests for layout, callbacks, helpers, configuration

**Integration Tests (34 tests):**

- `test_cassandra_endpoints.py`: API endpoint tests, response structure, demo mode

#### Verification, P3-7

- [x] Cassandra panel appears in dashboard tabs
- [x] Status badge shows UP/DOWN/DISABLED/UNAVAILABLE with colors
- [x] Demo mode returns synthetic cluster/metrics data
- [x] Cluster card displays contact points, keyspace, hosts table
- [x] Schema card displays keyspace count, table count, replication
- [x] Hosts table renders with UP/DOWN status badges
- [x] Auto-refresh via interval component
- [x] Error handling for connection failures
- [x] All 93 tests pass

#### Status, P3-7

**Status:** ✅ COMPLETE

---

## Implementation Summary

| Feature                        | Wave | Status      | Est. Effort | Coverage Impact                                 |
| ------------------------------ | ---- | ----------- | ----------- | ----------------------------------------------- |
| P3-1: Create New Snapshot      | 1    | ✅ Complete | M (1-3h)    | `hdf5_snapshots_panel.py`, `main.py`            |
| P3-2: Restore from Snapshot    | 1    | ✅ Complete | L (1-2d)    | `main.py`, `training_state_machine.py`          |
| P3-3: Snapshot History         | 1    | ✅ Complete | S-M (<3h)   | `hdf5_snapshots_panel.py`, `main.py`            |
| P3-4: Metrics Save/Load        | 2    | ✅ Complete | M (1-3h)    | `metrics_panel.py`, `main.py`                   |
| P3-5: 3D Topology View         | 2    | ✅ Complete | L (1-2d)    | `network_visualizer.py`                         |
| P3-6: Redis Monitoring Tab     | 3    | ✅ Complete | L (1-2d)    | New `redis_panel.py`, `redis_client.py`         |
| P3-7: Cassandra Monitoring Tab | 3    | ✅ Complete | XL (>2d)    | New `cassandra_panel.py`, `cassandra_client.py` |

---

## Verification Checklist

### P3-1: Create New Snapshot

- [x] Create button appears in HDF5 Snapshots panel
- [x] Name input allows custom snapshot names
- [x] Default name uses timestamp format
- [x] POST endpoint creates snapshot successfully
- [x] Demo mode creates mock snapshots
- [x] Success message displayed after creation
- [x] Table refreshes to show new snapshot
- [x] Error handling for creation failures

### P3-2: Restore from Snapshot

- [x] Restore button appears in each table row
- [x] Confirmation dialog before restore
- [x] Validation prevents restore during training
- [x] POST endpoint restores snapshot successfully
- [x] Training state updated after restore
- [x] WebSocket broadcasts state change
- [x] All UI components update correctly
- [x] Error handling for restore failures

### P3-3: Snapshot History

- [x] History section appears in panel
- [x] History entries display correctly
- [x] Create operations logged to history
- [x] Restore operations logged to history
- [x] History sorted by recency
- [x] Empty state handled gracefully

### P3-4: Metrics Save/Load

- [x] Save button appears in metrics panel
- [x] Name input allows custom layout names
- [x] POST endpoint creates layout successfully
- [x] Layouts persist to conf/layouts/
- [x] Load dropdown shows available layouts
- [x] Load button applies selected layout
- [x] Delete button removes layout
- [x] Success/error messages displayed
- [x] All 37 new tests pass

### P3-5: 3D Topology View

- [x] 2D/3D toggle appears in Network Topology panel
- [x] Default view is 2D
- [x] 3D renders Scatter3d traces
- [x] Nodes positioned by layer on z-axis
- [x] Edges colored by weight
- [x] Camera supports rotate/zoom/pan
- [x] Dark theme applies correctly
- [x] All 19 new tests pass
- [x] Existing 2D tests still pass

### P3-6: Redis Monitoring Tab

- [x] Redis panel appears in dashboard tabs
- [x] Status badge shows UP/DOWN/DISABLED/UNAVAILABLE with colors
- [x] Mode badge shows DEMO/LIVE/DISABLED
- [x] Demo mode returns synthetic metrics
- [x] Health card displays version, uptime, clients, latency
- [x] Metrics card displays memory, ops/sec, hit rate, keyspace
- [x] Auto-refresh via interval component (5s default)
- [x] Error handling for connection failures
- [x] Optional redis-py integration (fails soft)
- [x] All 140 new tests pass

### P3-7: Cassandra Monitoring Tab

- [x] Cassandra panel appears in dashboard tabs
- [x] Status badge shows UP/DOWN/DISABLED/UNAVAILABLE with colors
- [x] Mode badge shows DEMO/LIVE/DISABLED
- [x] Demo mode returns synthetic cluster/metrics data
- [x] Cluster card displays contact points, keyspace
- [x] Hosts table renders with UP/DOWN status badges
- [x] Schema card displays keyspace count, table count, replication
- [x] Auto-refresh via interval component (10s default)
- [x] Error handling for connection failures
- [x] Optional cassandra-driver integration (fails soft)
- [x] All 93 new tests pass

### Testing Requirements

- [x] All new tests pass (490 new tests for Wave 3 including coverage improvements)
- [x] Coverage maintained at 93%+ overall
- [x] No regressions in existing functionality (2903 tests passing, 39 skipped)
- [x] `hdf5_snapshots_panel.py` coverage improved from 54% to 95%
- [x] `about_panel.py` coverage improved from 73% to 100%
- [x] `main.py` coverage at 84% (up from 79%)
- [x] `redis_client.py` coverage at 97% (up from 76%)
- [x] `cassandra_client.py` coverage at 97% (up from 75%)
- [x] `redis_panel.py` coverage at 100% (up from 49%)
- [x] `cassandra_panel.py` coverage at 99%
- [x] `websocket_manager.py` coverage at 100% (up from 94%)
- [x] `statistics.py` coverage at 100% (up from 91%)
- [x] `dashboard_manager.py` coverage at 95% (up from 93%)

### Final Coverage Summary (2026-01-10)

| Component                 | Coverage | Target | Status           |
| ------------------------- | -------- | ------ | ---------------- |
| redis_panel.py            | 100%     | 95%    | ✅ Exceeded      |
| redis_client.py           | 97%      | 95%    | ✅ Exceeded      |
| cassandra_client.py       | 97%      | 95%    | ✅ Exceeded      |
| cassandra_panel.py        | 99%      | 95%    | ✅ Exceeded      |
| websocket_manager.py      | 100%     | 95%    | ✅ Exceeded      |
| statistics.py             | 100%     | 95%    | ✅ Exceeded      |
| dashboard_manager.py      | 95%      | 95%    | ✅ Met           |
| training_monitor.py       | 95%      | 95%    | ✅ Met           |
| training_state_machine.py | 96%      | 95%    | ✅ Exceeded      |
| main.py                   | 84%      | 95%    | ⚠️ Near target   |

**Note:** main.py remaining uncovered lines require real CasCor backend or uvicorn runtime entry point, which cannot be unit tested without integration environment.
