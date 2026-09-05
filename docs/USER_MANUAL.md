# Juniper Canopy User Manual

**Version:** 0.26.2
**Status:** ✅ Production Ready
**Last Updated:** September 5, 2026
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Training Controls](#training-controls)
5. [Visualization Tabs](#visualization-tabs)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)

---

## Introduction

### What is Juniper Canopy?

Juniper Canopy is a real-time monitoring and diagnostic frontend for Cascade Correlation (CasCor) Neural Networks. It provides:

- **Real-time Training Visualization** - Monitor loss, accuracy, and training progress
- **Network Topology Viewer** - Visualize network structure as it evolves
- **Decision Boundary Plotting** - See how the network classifies data
- **Dataset Explorer** - View and analyze training data
- **Training Controls** - Start, pause, resume, and reset training sessions

### Key Features

✅ **Zero Configuration** - Works out of the box with sensible defaults
✅ **Demo Mode** - Test and explore without a CasCor backend
✅ **Real-time Updates** - WebSocket-based push updates (<100ms latency)
✅ **Responsive UI** - Modern Bootstrap-based interface
✅ **Production Ready** - Comprehensive testing and CI/CD pipeline

---

## Getting Started

### Installation

1. **Clone the repository:**

   ```bash
   cd ~/Development/python/Juniper/juniper-canopy
   ```

2. **Activate the conda environment:**

   The env name is versioned: each rebuild increments the suffix and renames the
   old env `*-DEPRECATED`. Discover yours with `conda env list | grep JuniperCanopy`.

   ```bash
   conda activate JuniperCanopy1   # live env; see the note above
   ```

3. **Verify dependencies:**

   ```bash
   pip install -r conf/requirements.txt
   ```

### Running the Application

#### Demo Mode (Recommended for First-Time Users)

Demo mode runs a simulated training session without requiring a CasCor backend:

```bash
./demo
```

This will:

- Start the FastAPI server at <http://127.0.0.1:8050>
- Initialize demo mode with spiral dataset
- Begin simulated training automatically
- Open the dashboard at <http://127.0.0.1:8050/dashboard/>

#### Service Mode (With the juniper-cascor Service)

To monitor real training, point canopy at a running juniper-cascor service (and at
juniper-data, which supplies the dataset generators):

```bash
# The juniper-cascor service: host port 8201 in the standard local layout
# (8200 inside the juniper-deploy containers)
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://localhost:8201

# The juniper-data service (shared, unprefixed name)
export JUNIPER_DATA_URL=http://localhost:8100

# Run application (the env name is versioned — see Installation)
cd src
/opt/miniforge3/envs/JuniperCanopy1/bin/python main.py
```

Without `JUNIPER_CANOPY_CASCOR_SERVICE_URL` canopy logs
`No CasCor service URL configured — falling back to demo mode` and runs the demo backend.

### Accessing the Dashboard

Once running, open your browser to:

```bash
http://127.0.0.1:8050/dashboard/
```

You should see:

- **Status Indicator** (Green ● Active / Blue ● Training)
- **WebSocket Connection Status**
- **Training Controls Panel** (left sidebar)
- **Network Information Panel** (left sidebar)
- **Visualization Tabs** (main area)

---

## Dashboard Overview

### Layout Structure

```bash
┌─────────────────────────────────────────────────────────┐
│              Juniper Canopy Monitor                     │
│    Real-time monitoring for Cascade Correlation NNs     │
├──────────────┬──────────────────────────────────────────┤
│ Status: ●    │ WebSocket: 1 connection(s)               │
├──────────────┴──────────────────────────────────────────┤
│ Training     │ ┌─────────────────────────────────────┐  │
│ Controls     │ │  [Training Metrics Tab]             │  │
│ ┌─────────┐  │ │                                     │  │
│ │ Start   │  │ │  Loss and Accuracy plots            │  │
│ │ Pause   │  │ │                                     │  │
│ │ Stop    │  │ └─────────────────────────────────────┘  │
│ └─────────┘  │                                          │
│              │                                          │
│ Network      │                                          │
│ Info         │                                          │
│ ┌─────────┐  │                                          │
│ │Input: 2 │  │                                          │
│ │Hidden:3 │  │                                          │
│ │Output:1 │  │                                          │
│ └─────────┘  │                                          │
└──────────────┴──────────────────────────────────────────┘
```

### Status Indicators

#### System Status (Top Left)

- 🟢 **Green ● Active** - Server running, idle
- 🔵 **Blue ● Training** - Training in progress
- 🟠 **Orange ● Standby** - Server connected, not healthy
- 🔴 **Red ● Error** - Connection or server error

#### WebSocket Status (Top Right)

- **`N connection(s)`** (Green) - Active WebSocket connections
- **Disconnected** (Gray) - No WebSocket connection

### Update Intervals

- **Fast Updates** (1 second): Status indicators, training metrics
- **Slow Updates** (5 seconds): Network topology, decision boundaries, dataset

---

## Training Controls

The **Training Controls Panel** (left sidebar) provides real-time control over training:

### Control Buttons

#### Start Training

```bash
┌─────────────────┐
│  Start Training │  (Green)
└─────────────────┘
```

- **Action:** Starts or restarts training from beginning
- **Demo Mode:** Begins simulated training with automatic epoch progression
- **Production Mode:** Initiates training on real CasCor backend
- **Note:** Automatically resets state on start

#### Pause Training

```bash
┌─────────────────┐
│  Pause Training │  (Yellow/Warning)
└─────────────────┘
```

- **Action:** Pauses training without losing state
- **Demo Mode:** Freezes epoch progression while maintaining current state
- **Production Mode:** Sends pause command to CasCor backend
- **Resume:** Click again to resume (button text changes)

#### Stop Training

```bash
┌─────────────────┐
│  Stop Training  │  (Red/Danger)
└─────────────────┘
```

- **Action:** Stops training completely
- **Demo Mode:** Halts simulation thread cleanly
- **Production Mode:** Sends stop command to CasCor backend
- **Warning:** State is preserved but training cannot be resumed (use Start to restart)

### Configuration Parameters

The sidebar's **Meta Parameters** cards (Neural Network, Dataset, Candidate Nodes) hold the full
parameter set — epochs, learning rate, hidden units, multi-node layers, optimizer, activation,
output-weight initialisation, dataset generator fields and the candidate-pool settings. The two
below are the ones most often changed. Their bounds come from `TrainingSettings` in
`src/settings.py`, and their defaults can be overridden per deployment with
`JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT` / `JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT`
(see [Configuration](#configuration)). Edits are staged until you click **Apply** — the button
enables only when a value differs from the last applied set — and the **Parameters** tab shows the
applied values.

#### Learning Rate

- **Type:** Decimal number (any step)
- **Default:** 0.01
- **Range:** 0.0001 - 1.0
- **Effect:** Controls training speed and convergence

#### Maximum Hidden Units

- **Type:** Integer (step: 1)
- **Default:** 1000
- **Range:** 0 - 10000
- **Effect:** Caps the number of cascade units added during training

> **Note:** These controls are active in both demo and service modes.
> In service mode, current values are also exposed through `GET /api/status` and `GET /api/state`.

---

## Visualization Tabs

The dashboard ships **15 tabs**, in tab-bar order: [Training Metrics](#training-metrics-tab),
[Candidate Metrics](#candidate-metrics-tab), [Network Topology](#network-topology-tab),
[Network Evolution](#network-evolution-tab), [Decision Boundary](#decision-boundary-tab),
[Dataset View](#dataset-view-tab), [Workers](#workers-tab), [Parameters](#parameters-tab),
[Snapshots](#snapshots-tab), [Replay](#replay-tab), [Network Editor](#network-editor-tab),
[Redis](#redis-tab), [Cassandra](#cassandra-tab), [Tutorial](#tutorial-tab) and
[About](#about-tab). The five cascade-only tabs — Candidate Metrics, Network Topology, Network
Evolution, Decision Boundary and Workers — are hidden while a one-shot model such as
*Recurrence (LMU)* is selected.

### Training Metrics Tab

**Purpose:** Monitor real-time training progress with loss and accuracy curves

**Plots Displayed:**

1. **Training & Validation Loss** (Blue/Red lines)
2. **Training & Validation Accuracy** (Green/Orange lines)

**Features:**

- **Auto-scaling Y-axis** - Adjusts to data range
- **Real-time Updates** - Store updated every second (REST + WebSocket-assisted buffering)
- **Smoothing** - 10-point rolling average (configurable)
- **Hover Information** - Epoch, exact metric values
- **Legend Toggle** - Click legend items to show/hide series
- **Validation Overlays** - Dashed `val_loss` and `val_accuracy` traces are shown when available
- **Learning Rate Card** - Displays current `learning_rate` from training state (`--` if unavailable)
- **Hidden Units Ratio** - Displays `hidden_units / max_hidden_units` when max is known
- **Phase Duration** - Shows elapsed time from `phase_started_at` during active phases
- **Progress Bars** - Shows grow iteration and candidate epoch progress when state includes:
  - `grow_iteration`, `grow_max`
  - `candidate_epoch`, `candidate_total_epochs`

**Interpreting the Plots:**

✅ **Good Training:**

- Loss decreases smoothly
- Accuracy increases steadily
- Validation metrics track training metrics closely
- No sudden spikes or divergence

⚠️ **Warning Signs:**

- Validation loss increases while training loss decreases (overfitting)
- Erratic fluctuations (learning rate too high)
- Flat curves (learning rate too low, or convergence)

**Metric Layouts:** name the current zoom/pan view and click **Save Layout**
(`POST /api/v1/metrics/layouts`); the dropdown lists the saved layouts (`GET /api/v1/metrics/layouts`),
**Load** re-applies one and **Delete** removes it without a confirmation dialog.

**In-metrics replay:** when training is stopped, paused, completed or failed (never during a live
run) a replay bar appears under the plots: ⏮ start, ◀ step back, ▶ play / ⏸ pause, step forward,
⏭ end, a position slider and a `current / max` readout. Playback advances one recorded epoch per
tick. The base tick is **1000 ms**; the **1x / 2x / 4x** buttons set it to 1000 / 500 / 250 ms.

**Data Source:**

- Metrics history: `GET /api/metrics/history?limit=...`
- Training state: `GET /api/state`
- WebSocket stream: `/ws/training` (`metrics`, `state`, `topology`, `event`)

---

### Network Topology Tab

**Purpose:** Visualize network architecture and connection weights

**Display Elements:**

1. **Input Nodes** (Green circles, left)
   - One node per input feature
   - Default: 2 nodes for (x, y) coordinates

2. **Hidden Nodes** (Blue circles, middle)
   - Cascade units added during training
   - Count increases as training progresses
   - Maximum: 8 in demo mode (configurable)

3. **Output Nodes** (Orange circles, right)
   - One node per output class
   - Default: 1 node for binary classification

4. **Connection Lines**
   - **Color Intensity** - Represents weight magnitude
   - **Red** - Negative weights
   - **Blue** - Positive weights
   - **Thickness** - Proportional to |weight| value

**Layout Algorithm:**

- **Spring Layout** - Nodes positioned by force-directed graph
- **Layered** - Input (layer 0) → Hidden (layer 1) → Output (layer 2)

**Interactive Features:**

- **Zoom** - Scroll to zoom in/out
- **Pan** - Click and drag to pan view
- **Hover** - Show node ID and connection details
- **Hidden depth slider** - Once at least one cascade unit exists, filter the graph to the first `K` hidden units (see below)

**Hidden Depth Filter:**

The **Hidden depth** slider is a view filter, not a training control. CasCor adds hidden units in cascade order (`hidden_0` first), so the slider shows a prefix of that history.

| Slider / label | What you see |
| --- | --- |
| Label reads **`all`** | No filter. Every hidden unit and every connection is drawn. |
| Label reads **`K of N`** | Only the first `K` of `N` hidden units. Edges that touch a hidden unit at or past `K` are dropped. |
| Slider at rest (`0`) | Same as **`all`**. `0` means "no filter", not "show zero units." |
| Slider at max (`N`) | Same as **`all`**. |

The slider is hidden until the network has at least one hidden unit. Dragging commits on mouse-up (not on every tick). A chosen `K` survives later `cascade_add` events unless it is now past the new max, in which case the control snaps to "show all." The stats bar's Hidden Units readout shows `K of N` while a filter is active.

The first-run walkthrough highlights this control (`network-visualizer-depth-slider-container`).

If the label stays at `"0 of N"` while the graph is clearly showing every unit, that is F-CANOPY-042 (the label was wired to topology changes, not to the slider, and treated rest-state `0` as a real depth). The graph and stats bar can still be correct. canopy#570 splits the label onto its own clientside callback so it tracks the slider and matches the filter. See [AGENTS_REFERENCE.md § Hierarchy Depth Filter](AGENTS_REFERENCE.md#hierarchy-depth-filter-can-020).

- **Click a node** - Opens the selection panel (`Selected: …`, `Layer: Input|Hidden|Output`). Clicking the same node again clears the selection.
- **Box / lasso** - Mode-bar `select2d` / `lasso2d` select several nodes. The panel lists up to five.

**Node Selection:**

The selection panel is view state. It highlights nodes on the graph; it does not change the trained network.

| Gesture | What happens |
| --- | --- |
| Click a node (or the edge vertex that sits on it) | Panel opens. Layer is taken from the node *label* (`Hidden 0` → Hidden), not from the Plotly curve index. |
| Click the selected node again | Selection clears. This is the only *canvas* click gesture that clears; the **Clear selection** button clears too. |
| Click any member of a box/lasso set | The *whole* set clears (same toggle). |
| Click empty canvas | **Nothing.** Plotly emits `plotly_click` only when a point is hit. The callback never runs. |

The panel *used to say* *"(Click again or elsewhere to deselect)"* after a click and *"(Click elsewhere to deselect)"* after a box select. The "elsewhere" half was described but never implemented. canopy#573 fixed it: a **Clear selection** button appears only while something is selected, the click hint reads *"(Click again to deselect)"*, and the box/lasso panel carries no hint, because the button is the affordance. See [AGENTS_REFERENCE.md § Topology Node Selection](AGENTS_REFERENCE.md#topology-node-selection-f-canopy-046).

- **Camera (modebar)** — download the current figure as PNG
  (`canopy_network_<YYYYmmdd>_<HHMMSS>.png`, 2× scale). SVG from the
  same menu is a different path and does not need `blob:`. If the
  camera button does nothing, the browser console will show a CSP
  `img-src` violation — see
  [troubleshooting #6](#6-modebar-camera-does-nothing-no-png-file).

**Data Source:**

- API: `GET /api/topology`
- WebSocket: `/ws/training` (type: `topology`)

**Example Topology Response:**

```json
{
  "input_units": 2,
  "hidden_units": 3,
  "output_units": 1,
  "nodes": [
    {"id": "input_0", "type": "input", "layer": 0},
    {"id": "input_1", "type": "input", "layer": 0},
    {"id": "hidden_0", "type": "hidden", "layer": 1},
    {"id": "hidden_1", "type": "hidden", "layer": 1},
    {"id": "hidden_2", "type": "hidden", "layer": 1},
    {"id": "output_0", "type": "output", "layer": 2}
  ],
  "connections": [
    {"from": "input_0", "to": "output_0", "weight": 0.234},
    {"from": "input_1", "to": "output_0", "weight": -0.156},
    {"from": "hidden_0", "to": "output_0", "weight": 0.678}
  ],
  "total_connections": 9
}
```

---

### Network Editor Tab

**Purpose:** Make surgical edits to a restored CasCor network snapshot.

The Network Editor is for service-mode investigation workflows, not normal training. It is disabled until the CasCor lifecycle reports the `Investigating` state, which is entered by restoring a snapshot from the Snapshots tab. The panel polls `GET /api/status` every 2 seconds and unlocks when `state_machine.status` is `Investigating`.

**Available Operations:**

1. **Append Hidden Unit**
   - Adds one hidden unit at the cascade tail.
   - The weight vector length must match `input_size + existing_hidden_units`.
   - `bias` defaults to `0.0`.
   - Supported UI activation choices are `Tanh`, `Sigmoid`, `ReLU`, and `Linear`.
   - CasCor initializes the new unit's output column to zero, so the unit has no output-layer effect until weights are patched or training is resumed.

2. **Remove Hidden Unit**
   - Deletes the selected zero-based hidden unit index.
   - CasCor rebuilds downstream cascade weights so the forward-pass shape invariant still holds.
   - The optimizer state is dropped on the CasCor side and rebuilt by fresh training.

3. **Patch Weights**
   - Patches one parameter group:
     - `output_weights`
     - `output_bias`
     - `hidden_unit_weights`
     - `hidden_unit_bias`
   - `hidden_unit_*` targets require a hidden unit index.
   - Values can be entered as comma-, semicolon-, or newline-separated floats.
   - Canopy sends `dtype: "float32"` and lets CasCor validate the exact target shape.

**Workflow:**

1. Run Canopy in service mode against a live CasCor backend.
2. Restore a snapshot from the Snapshots tab.
3. Wait for the Network Editor badge to show `FSM: Investigating`.
4. Review the topology readout and hidden unit indexes.
5. Apply the smallest mutation needed.
6. Use the API response shown in the status alert to confirm the edit.
7. Resume or retrain from the edited snapshot when ready.

**Constraints and Failure Modes:**

- Demo mode cannot apply network mutations; Canopy returns `501 Not Implemented` for the proxy routes.
- CasCor enforces the `Investigating` lifecycle gate and rejects mutation attempts from other states.
- CasCor owns exact tensor shape checks, out-of-range hidden unit handling, NaN/Inf validation, and activation validation.
- Canopy currently surfaces adapter failures as status alerts using the backend `detail` text.
- Destructive operations should be treated as snapshot-scoped edits; keep an original snapshot available before removing units or replacing large weight groups.

**Data Sources:**

- Gating status: `GET /api/status`
- Public topology API: `GET /api/topology`
- Mutations:
  - `PATCH /api/v1/network/weights`
  - `POST /api/v1/network/hidden-units`
  - `DELETE /api/v1/network/hidden-units/{idx}`

**Troubleshooting:**

- If the topology readout does not refresh after the editor unlocks, verify the panel's internal topology request path in `src/frontend/components/network_editor_panel.py` matches the public `GET /api/topology` route exposed by `src/main.py`.

**Example Patch Request:**

```json
{
  "target": "hidden_unit_weights",
  "field": "weights",
  "values": [0.12, -0.04, 0.31],
  "hidden_unit_index": 2,
  "dtype": "float32"
}
```

---

### Decision Boundary Tab

**Purpose:** Visualize how the network classifies the input space

**Display Components:**

1. **Contour Plot** (Background)
   - **Color Gradient** - Represents classification confidence
   - **Viridis Colorscale** - Purple (class 0) → Yellow (class 1)
   - **Resolution** - 100x100 grid (configurable)

2. **Data Points** (Scatter overlay)
   - **Color** - Actual class label
   - **Size** - Fixed (5 pixels)
   - **Opacity** - 70% for background visibility

**Interpreting the Visualization:**

✅ **Good Classification:**

- Clear separation between color regions
- Data points clustered in correct color regions
- Smooth decision boundaries

⚠️ **Poor Classification:**

- Mixed colors in data point regions
- Erratic, noisy boundaries
- Points in wrong color regions (misclassifications)

**Configuration Options** (app_config.yaml):

```yaml
frontend:
  decision_boundary:
    resolution: 100        # Grid resolution
    opacity: 0.7           # Contour opacity
    contour_levels: 20     # Number of contour lines
    color_scale: Viridis   # Colormap
    show_data_points: true
    show_misclassified: true
```

**Data Source:**

- API: `GET /api/decision_boundary`
- Computed on-demand from network forward pass

**Example Response:**

```json
{
  "xx": [[...], [...], ...],    // X-coordinate meshgrid
  "yy": [[...], [...], ...],    // Y-coordinate meshgrid
  "Z": [[...], [...], ...],     // Predictions (100x100)
  "bounds": {
    "x_min": -1.2,
    "x_max": 1.2,
    "y_min": -1.2,
    "y_max": 1.2
  }
}
```

---

### Dataset View Tab

**Purpose:** Explore the training dataset structure and distribution

**Display Elements:**

1. **Scatter Plot** (2D data points)
   - **X-axis** - Feature 1 (e.g., x-coordinate)
   - **Y-axis** - Feature 2 (e.g., y-coordinate)
   - **Color** - Class label
   - **Marker Size** - 5 pixels

2. **Statistics Panel** (if enabled)
   - Sample count
   - Feature count
   - Class distribution

**Default Dataset (Demo Mode):**

- **Name:** Two-Class Spiral
- **Samples:** 200 (100 per class)
- **Features:** 2 (x, y coordinates)
- **Classes:** 2 (binary)
- **Noise:** Gaussian (σ=0.1)

**Loading a dataset:**

- **Service mode (juniper-cascor backend):** datasets come from the juniper-data service. In the
  sidebar's **Dataset** section pick a generator (the list is `GET /api/dataset/generators`, proxied
  from juniper-data), fill in its parameters and click **Apply** (`POST /api/stage_dataset`). The
  staged dataset takes effect through **Restart with new dataset** (`POST /api/train/restart`) or —
  with **Experimental Functions** enabled and a run in progress — the **Live Switch**
  (`POST /api/live_dataset_swap`).
- **Demo mode only:** this tab's **Generate / Upload / URL** modal — `POST /api/dataset/generate`
  (built-in generators), `POST /api/dataset/import-file` (CSV upload) and
  `POST /api/dataset/import-url` (a CSV fetched by the server; disabled unless
  `JUNIPER_CANOPY_DATASET_IMPORT_URL_ENABLED=true`). Both import paths accept **CSV only**: one
  sample per row, the last column is the integer class label, a header row is auto-detected, and
  files are capped at 10 MB / 50 000 rows / 100 features. JSON, NumPy `.npy` and HDF5 `.h5` files
  are **not** accepted. In service mode all three actions are refused with HTTP `400`.

**Data Source:**

- API: `GET /api/dataset`

**Service Mode Behavior:**

- Service-mode responses may include metadata only (`num_samples`, `num_features`, `num_classes`) when arrays are not available yet.
- In that case, the dataset tab renders empty plots with summary stats and class distribution shown as `N/A`.
- When arrays are available, `inputs` and `targets` are rendered normally.

**Example Response:**

```json
{
  "inputs": [[0.12, 0.34], [-0.56, 0.78], ...],
  "targets": [0, 1, 0, 1, ...],
  "num_samples": 200,
  "num_features": 2,
  "num_classes": 2
}
```

---

### Candidate Metrics Tab

**Purpose:** Follow the candidate pool while cascor trains candidate units (the phase between
output-training passes)

**Display Elements:**

1. **Pool Status Badge**, **Phase** (`Idle` until a pool is active) and **Pool Size**
2. **Candidate Epoch Progress** — `epoch / total`, shown only while the training state carries
   `candidate_epoch` and `candidate_total_epochs`
3. **Current Pool** (collapsible) — "No active candidate pool" or the per-candidate view
4. **Candidate Loss Plot** — the candidate epochs of the current run, read from the same metrics
   store as the Training Metrics tab (no extra polling)
5. **Pool History** (collapsible) — one read-only card per finished pool, capped at the most recent
   entries

**Data Source:**

- The training-state and metrics stores shared with the Training Metrics tab; the tab's own refresh
  runs only while it is selected

---

### Network Evolution Tab

**Purpose:** A gallery of the network's cascade growth — one card per hidden unit added during a run

**Display Elements:**

1. **Stats line** — "No snapshots yet" until the first unit is added
2. **Snapshot grid** — one card per growth step, captured in the browser from the `cascade_add`
   WebSocket events and the current topology; a step with an unchanged hidden-unit count is skipped,
   and the gallery clears itself when the input width changes or the hidden-unit count shrinks (a
   dataset change or a reset)
3. **Clear** — empties the gallery
4. **Weight norms** — per-unit weight-norm traces, revealed only while a snapshot replay streams
   weight samples (see [Replay Tab](#replay-tab))

The sidebar is hidden on this tab.

**Data Source:**

- WebSocket stream `/ws/training` (`cascade_add` events) and the topology store — no polling

---

### Workers Tab

**Purpose:** Read-only view of the cascor worker registry

**Display Elements:**

1. **Status Badge** — `LOADING`, then `NO WORKERS`, `DEGRADED` (stale workers present) or `HEALTHY`
2. **Degradation alert** — "Worker data degraded: …" when the upstream call fails (dismissable)
3. **Six tiles** — total, idle, busy, stale, tasks done (`done / failed fail`) and average health
4. **Roster table** — id, kind (`local` / `remote`), status, health, last heartbeat, current task —
   or "No workers connected"
5. **Local-workers note** — cascor's registry reports remote WebSocket workers only; the in-process
   candidate pool is not listed individually, and the panel says so rather than inventing rows

**Data Source:**

- `GET /api/v1/workers/list` (roster) plus best-effort aggregate stats, polled on the slow interval
  only while this tab is selected

---

### Parameters Tab

**Purpose:** At-a-glance, read-only summary of the applied meta-parameters

**Display Elements:**

1. **Network Training**, **Dataset** and **Candidate Training** tables — Pin / Parameter / Current /
   Min / Max / Default; booleans render as `Enabled` / `Disabled`
2. **Pin checkboxes** — pinned parameters appear as read-only name + value rows in the sidebar's
   **Pinned** card; the pin set lives in browser local storage, so it survives a reload

Editing happens in the sidebar; the tables re-render after every **Apply**.

**Data Source:**

- The applied-parameters store (filled by the sidebar's **Apply** round-trip) — no polling

---

### Snapshots Tab

**Purpose:** Create, browse and act on HDF5 training-state snapshots

**Display Elements and Controls:**

1. **Create** — optional name and description, then **Create Snapshot** (`POST /api/v1/snapshots`);
   the form clears on success and the table refreshes
2. **Snapshot table** — auto-refreshes every 10 s (`JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS`)
   and on **Refresh**; in service mode the list comes from the cascor service that created the
   snapshots, with canopy's local snapshot directory as the fallback
3. **View** — opens the detail panel (`GET /api/v1/snapshots/{id}`)
4. **Restore / Replay / Resume / Retrain** — per row, or from the right-click context menu; each
   opens a confirmation modal, and **Confirm** posts `POST /api/v1/snapshots/{id}/{op}`. Training
   must be paused or stopped first: a running run answers `409`, an unknown id `404`, an operation
   the backend does not support `501`
5. **Replay** additionally loads the session into the [Replay Tab](#replay-tab) and switches to it
6. **History** (collapsible) — `GET /api/v1/snapshots/history`
7. **Dataset swaps** — paired before / after cards for every live dataset swap recorded in the run

**Data Source:**

- `GET /api/v1/snapshots`, `GET /api/v1/snapshots/{id}`, `GET /api/v1/snapshots/history`,
  `POST /api/v1/snapshots`, `POST /api/v1/snapshots/{id}/{restore|replay|resume|retrain}`

---

### Replay Tab

**Purpose:** Drive a snapshot replay session opened from the Snapshots tab

**Display Elements and Controls:**

1. **Idle placeholder** — "No active replay session" until a replay is confirmed on the Snapshots tab
2. **Session header** — snapshot id, FSM badge, and a weights badge (`V2 ✓ weights` when the
   snapshot carries weights, otherwise `V1 (metrics only)`)
3. **Transport** — ▶ Play, ⏸ Pause, ⏹ Stop
4. **Epoch scrubber** — drag and release to seek; readout `current / end`
5. **Speed slider** — −10× … 10×; negative values play backwards, 0 pauses (`Paused (0×)`)
6. **Time range** — restrict playback to a sub-window of epochs
7. **Status block** — the result of the last control action
8. **Dataset-swap events** — markers on a wall-clock axis with a count; hover for details

Every control posts `POST /api/v1/snapshots/{id}/replay/control`, which canopy proxies to the cascor
service. Weight samples streamed during playback are drained every 500 ms into the buffer that feeds
the [Network Evolution](#network-evolution-tab) weight-norm traces.

**Data Source:**

- `POST /api/v1/snapshots/{id}/replay/control`; the loaded snapshot's swap history from
  `GET /api/snapshots/{id}/history/dataset_swaps`

---

### Redis Tab

**Purpose:** Read-only monitoring of the optional Redis cache integration

**Display Elements:**

1. **Status** and **Mode** badges (`DEMO` / `LIVE` / `DISABLED`)
2. **Unavailable / error display** — when no Redis is deployed the tab shows an unavailable state and
   leaves the rest of the dashboard untouched
3. **Eight tiles** — version, uptime, connected clients, latency, memory, ops/sec, hit rate and
   keyspace (placeholders when unavailable)

**Data Source:**

- `GET /api/v1/redis/status` and `GET /api/v1/redis/metrics`, every 5 s

---

### Cassandra Tab

**Purpose:** Read-only monitoring of the optional Cassandra persistence integration

**Display Elements:**

1. **Status** (`UP` / `DOWN` / `DISABLED` / `UNAVAILABLE`) and **Mode** (`DEMO` / `LIVE` /
   `DISABLED`) badges
2. **Error area** — an unavailable render, never a crash, when no cluster is configured
3. **Cluster overview** — contact points, keyspace, a hosts table, keyspace count, table count and
   replication strategies (placeholders when unavailable)

**Data Source:**

- `GET /api/v1/cassandra/status` and `GET /api/v1/cassandra/metrics`, every 10 s

---

### Tutorial Tab

**Purpose:** In-app orientation

**Display Elements and Controls:**

1. **▶ Take a guided tour** — launches the walkthrough overlay (Skip / Done to leave it)
2. **Accordion** — CasCor overview, workflow, UI guide, parameter reference and keyboard shortcuts;
   sections open independently of each other
3. Right-clicking a control that has a tooltip offers **View tutorial**, which jumps to this tab

---

### About Tab

**Purpose:** Application information

**Display Elements:**

1. **App Version** — the installed package version, the same value `GET /v1/health` reports
2. Licence, credits, documentation links and contact information
3. **System Information** (toggle) — Python version and platform details, built locally without a
   request

---

## Configuration

### Configuration Files

Settings are typed `pydantic-settings` models in `src/settings.py`; the only configuration *file* the
application reads is an optional `.env` in the working directory (`.env.example` documents every
key). Precedence, highest first:

1. Environment variables (`JUNIPER_CANOPY_*`, see below)
2. The `.env` file
3. The defaults in `src/settings.py`

`conf/app_config.yaml` is **legacy**: the application settings no longer come from it (only the
optional Redis client still reads it, through `config_manager.py`).

### Environment Variables

Every setting has a `JUNIPER_CANOPY_`-prefixed environment variable; nested sections use a double
underscore:

```bash
# Server configuration
export JUNIPER_CANOPY_SERVER__PORT=8051
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0   # a non-loopback host needs a SEC-F22 attestation — see .env.example

# Demo mode
export JUNIPER_CANOPY_DEMO_MODE=1

# Backend path
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://localhost:8201    # juniper-cascor service (service mode)
export JUNIPER_DATA_URL=http://localhost:8100                      # juniper-data (shared, unprefixed)
export JUNIPER_CANOPY_BACKEND_PATH=/custom/path/to/juniper-cascor  # in-process cascor checkout (legacy path)

# Debug mode
export JUNIPER_CANOPY_SERVER__DEBUG=true
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG
export JUNIPER_CANOPY_LOG_FORMAT=json

# Sidebar defaults for the training parameters
export JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT=0.01
export JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT=1000
export JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=1000000

# Demo-mode pacing
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=30      # add a cascade unit every N epochs
# JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL is declared in settings but not applied: the backend
# factory creates the demo backend with a fixed 1.0 s epoch interval (a tracked divergence).
```

**Legacy `CASCOR_*` names.** `CASCOR_DEMO_MODE`, `CASCOR_SERVICE_URL`, `CASCOR_BACKEND_PATH`,
`CASCOR_LOG_LEVEL`, `CASCOR_DEMO_UPDATE_INTERVAL` and `CASCOR_DEMO_CASCADE_EVERY` are still honoured,
with a deprecation warning at startup. **`CASCOR_SERVER_PORT`, `CASCOR_SERVER_HOST` and `CASCOR_DEBUG`
are read by nothing** — exporting them has no effect; use the `JUNIPER_CANOPY_SERVER__*` names above.
The sidebar's training defaults additionally honour the unprefixed `CASCOR_TRAINING_LEARNING_RATE`,
`CASCOR_TRAINING_HIDDEN_UNITS` and `CASCOR_TRAINING_EPOCHS`.

### Key Configuration Sections

Every setting below lives on `Settings` in `src/settings.py`; the environment name is the field name
upper-cased under the `JUNIPER_CANOPY_` prefix, with `__` between a nested section and its key.

#### Application Settings

| Setting (`src/settings.py`)                   | Environment variable                                             | Default                        |
|-----------------------------------------------|------------------------------------------------------------------|--------------------------------|
| `server.host` / `server.port` / `server.debug` | `JUNIPER_CANOPY_SERVER__HOST` / `__PORT` / `__DEBUG`            | `127.0.0.1` / `8050` / `false` |
| `demo_mode`                                   | `JUNIPER_CANOPY_DEMO_MODE`                                       | `false`                        |
| `cascor_service_url`                          | `JUNIPER_CANOPY_CASCOR_SERVICE_URL`                              | unset (demo fallback)          |
| `juniper_data_url`                            | `JUNIPER_DATA_URL` (or `JUNIPER_CANOPY_JUNIPER_DATA_URL`)        | `http://localhost:8100`        |
| `recurrence_service_url`                      | `JUNIPER_CANOPY_RECURRENCE_SERVICE_URL`                          | unset                          |
| `training.<param>.{min,max,default}`          | `JUNIPER_CANOPY_TRAINING__<PARAM>__{MIN,MAX,DEFAULT}`            | see `TrainingSettings`         |
| `demo_cascade_every`                          | `JUNIPER_CANOPY_DEMO_CASCADE_EVERY`                              | `30`                           |
| `demo_update_interval`                        | `JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL` — declared, **not applied** (fixed 1.0 s) | `1.0`           |

#### Frontend Settings

| Setting                                       | Environment variable                                             | Default                        |
|-----------------------------------------------|------------------------------------------------------------------|--------------------------------|
| `enable_ws_control_buttons`                   | `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS`                       | `true`                         |
| `dataset_import_url_enabled`                  | `JUNIPER_CANOPY_DATASET_IMPORT_URL_ENABLED`                      | `false`                        |
| Snapshots-table refresh (panel-local)         | `JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS`                   | `10000`                        |

#### Logging Settings

| Setting                                       | Environment variable                                             | Default                        |
|-----------------------------------------------|------------------------------------------------------------------|--------------------------------|
| `log_level` / `log_format`                    | `JUNIPER_CANOPY_LOG_LEVEL` / `JUNIPER_CANOPY_LOG_FORMAT`         | `INFO` / `text`                |
| `sentry_dsn`                                  | `JUNIPER_CANOPY_SENTRY_DSN`                                      | unset                          |
| `metrics_enabled`                             | `JUNIPER_CANOPY_METRICS_ENABLED`                                 | `false`                        |

### Applying Configuration Changes

1. Export the variable (or edit `.env`) in the shell that will launch canopy.
2. Restart the application (`./demo`, or the service-mode command above) — settings are read once at
   startup.
3. Verify: the startup log carries a deprecation warning for every legacy name in use, and
   `GET /v1/health` reports `demo_mode`.

---

## Troubleshooting

### Common Issues

#### 1. "No data available" in Dashboard Tabs

**Symptoms:**

- All tabs show "No data available"
- Metrics, topology, dataset views are empty

**Causes:**

- Demo mode not started
- WebSocket not connected
- API endpoint errors

**Solutions:**

✅ **Check demo mode is running:**

```bash
# In logs/system.log, look for:
"Demo mode started with simulated training"
"Demo training simulation started"
```

✅ **Verify WebSocket connection:**

- Check "WebSocket: 1 connection(s)" in dashboard header
- If "Disconnected", refresh browser page

✅ **Check API endpoints:**

```bash
curl http://127.0.0.1:8050/api/health
curl http://127.0.0.1:8050/api/metrics?limit=10
```

✅ **Review logs for errors:**

```bash
tail -f logs/system.log | grep -i error
```

---

#### 2. ModuleNotFoundError: No module named 'uvicorn'

**Symptoms:**

```bash
ModuleNotFoundError: No module named 'uvicorn'
```

**Cause:**

- Using system Python instead of conda environment

**Solutions:**

✅ **Use conda environment Python explicitly:** (the env name is versioned;
discover yours with `conda env list | grep JuniperCanopy`)

```bash
/opt/miniforge3/envs/JuniperCanopy1/bin/python main.py
```

✅ **Or activate environment first:**

```bash
conda activate JuniperCanopy1
python main.py
```

✅ **Use demo script (automatically activates):**

```bash
./demo
```

---

#### 3. Port Already in Use

**Symptoms:**

```bash
Error: Address already in use: 127.0.0.1:8050
```

**Cause:**

- Another instance running on same port
- Previous instance didn't shut down cleanly

**Solutions:**

✅ **Find and kill existing process:**

```bash
# Find process using port 8050
lsof -i :8050

# Kill process
kill -9 <PID>
```

✅ **Use different port:**

```bash
export JUNIPER_CANOPY_SERVER__PORT=8051
./demo
```

---

#### 4. Demo Mode Won't Stop

**Symptoms:**

- Ctrl+C doesn't stop application
- Training continues after stop button

**Cause:**

- Background thread not stopping cleanly

**Solutions:**

✅ **Force kill:**

```bash
# Find Python process
ps aux | grep python | grep main.py

# Kill
kill -9 <PID>
```

✅ **Check Event-based stopping:**

```python
# In demo_mode.py, verify:
while not self._stop.is_set():
    # ... work
```

---

#### 5. WebSocket Connection Failures

**Symptoms:**

- "WebSocket: Disconnected" in dashboard
- No real-time updates
- Browser console shows WebSocket errors

**Causes:**

- FastAPI event loop not set
- Network/firewall issues
- CORS configuration

**Solutions:**

✅ **Verify event loop setup (in logs):**

```text
"Event loop captured for thread-safe broadcasting"
```

✅ **Check browser console:**

```javascript
// Should see:
WebSocket connection to 'ws://127.0.0.1:8050/ws/training' opened
```

✅ **Test WebSocket manually:**

```javascript
// In browser console:
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', e.data);
```

---

#### 6. Depth-filter label stuck at "0 of N" (F-CANOPY-042) — **fixed in canopy#570**

Kept for anyone running a build older than canopy#570. On current `main` the
label follows the slider and reads `"all"` at rest.

**Symptoms (pre-#570):**

- Network Topology tab shows a loaded cascade (for example 40 hidden units)
- The **Hidden depth** label reads `"0 of 40"` at rest, or does not change when you drag the slider
- The graph and the Hidden Units stats count still follow the filter

**Cause:**

- The label *was* a fourth output of the clientside slider-bounds sync. That callback fires only when the topology store changes; the slider value was read as State. Rest-state `0` was also rendered as `"0 of N"` even though the filter treats `0` as "show all."

**What to do:**

- Trust the graph and the stats bar for what is actually drawn. `"all"` and a slider at max are the no-filter states.
- Do not "fix" the label by adding the slider value as an Input of the bounds-sync callback — Dash rejects that as a circular dependency (`-depth-slider.value` is already an Output there).
- Do not route the label through the topology rebuild (`update_network_graph`); that callback's measured paint is 1.5–31 s.
- The repair, canopy#570, is on `main`: a dedicated clientside label callback whose rule matches `_apply_hierarchy_filter`. Developer contract: [AGENTS_REFERENCE.md § Hierarchy Depth Filter](AGENTS_REFERENCE.md#hierarchy-depth-filter-can-020).

---

#### 6. Topology selection does not clear when you click empty space — **fixed in canopy#573**

Kept for anyone running a build older than canopy#573. Clicking blank canvas
still does nothing — plotly emits no event — but the panel no longer promises
that it will, and a **Clear selection** button now carries the gesture.

**Symptoms (pre-#573):**

- After a click the panel read *"(Click again or elsewhere to deselect)"*
- After a box/lasso it read *"(Click elsewhere to deselect)"*
- Clicking the blank canvas left the highlight in place

- Plotly emits `plotly_click` only when a *point* is hit. A click on empty canvas produces no event, so `clickData` never changes and `handle_node_selection` (`prevent_initial_call=True`) never runs. The "elsewhere" sentence was never implemented.

**Solutions:**

✅ **Click the selected node again** — that toggle *does* clear (including every member of a box/lasso set).

✅ **Use the Clear selection button.** A clientside click-on-empty handler was considered and rejected (it races Plotly and starves the 1.5–31 s rebuild family); canopy#573 shipped an explicit **Clear selection** button instead, visible only while something is selected.

See [AGENTS_REFERENCE.md § Topology Node Selection](AGENTS_REFERENCE.md#topology-node-selection-f-canopy-046).

#### 6. Modebar camera does nothing (no PNG file)

- Topology (or any Plotly) camera button is present and clickable
- No file is offered; the figure does not change
- Browser console reports a Content-Security-Policy `img-src` violation
  for a `blob:http://…` URL

Plotly's PNG export rasterises SVG → Blob → `<img>` → canvas. That
image load is a `blob:` URL. The shipped policy is
`img-src 'self' data: blob:` (`SecurityConstants.DEFAULT_CSP_POLICY`,
served by `SecurityHeadersMiddleware`). Without `blob:`, the promise
rejects with `[object Event]` and no download is offered. SVG export
from the same menu still works.

✅ **Confirm the console names `img-src`**, not a missing figure.

✅ **Confirm the constant and the middleware still match:**

```bash
cd src
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v
```

Do not "fix" this by adding `blob:` to `script-src` or by replacing
`data:` (Bootstrap icons need `data:`). Developer contract:
[AGENTS_REFERENCE.md § Plotly PNG Export](AGENTS_REFERENCE.md#plotly-png-export-f-canopy-047).

### Diagnostic Commands

**Check server health:**

```bash
curl http://127.0.0.1:8050/api/health
```

**Get current status:**

```bash
curl http://127.0.0.1:8050/api/status
```

**Get metrics:**

```bash
curl http://127.0.0.1:8050/api/metrics?limit=5
```

**View logs:**

```bash
# System logs
tail -f logs/system.log

# Training logs
tail -f logs/training.log

# UI logs
tail -f logs/ui.log
```

**Check processes:**

```bash
ps aux | grep -i cascor
ps aux | grep -i python.*main.py
```

---

## Advanced Features

### Async Training (v0.25.0+)

Version 0.25.0 introduces asynchronous training capabilities via `CascorIntegration`:

- **`fit_async()`** - Non-blocking training with `ThreadPoolExecutor`
- **`start_training_background()`** - Background training with real-time status updates
- **RemoteWorkerClient integration** - Distributed training support
- **Thread-safe status tracking** - Monitor training progress from any thread

**Example Usage:**

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
future = integration.fit_async(X_train, y_train, max_epochs=200)

# Training runs in background - check status
while not future.done():
    status = integration.get_training_status()
    print(f"Epoch: {status['current_epoch']}")
```

> **Note:** Async training requires a real CasCor backend (not available in demo mode).

---

### WebSocket Real-Time Updates

Juniper Canopy uses WebSocket push updates for real-time data streaming:

**Connection:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Type:', msg.type, 'Data:', msg.data);
};
```

**Message Types:**

- `connection_established` - Initial connection confirmation
- `training_metrics` - Epoch metrics (loss, accuracy)
- `topology_update` - Network structure changes
- `cascade_add` - New hidden unit added
- `status` - Training status changes (paused, running, stopped)

**Latency:** <100ms for metric updates

---

### Custom Datasets

To use your own dataset in demo mode:

1. **Prepare data format:**

   ```python
   dataset = {
       "inputs": np.array([[x1, x2], [x1, x2], ...]),  # Shape: (N, 2)
       "targets": np.array([0, 1, 0, 1, ...]),         # Shape: (N,)
       "num_samples": N,
       "num_features": 2,
       "num_classes": 2
   }
   ```

2. **Modify demo_mode.py:**

   ```python
   def _generate_custom_dataset(self):
       # Load your data
       inputs = np.loadtxt('data/my_dataset.csv', delimiter=',')
       targets = np.loadtxt('data/my_labels.csv')

       return {
           "inputs": inputs,
           "targets": targets,
           # ... etc
       }
   ```

3. **Update initialization:**

   ```python
   self.dataset = self._generate_custom_dataset()
   ```

---

### Performance Tuning

**Reduce Update Frequency:**

```yaml
frontend:
  dashboard:
    update_interval_ms: 2000  # Slower updates (less CPU)
```

**Limit Data Points:**

```yaml
frontend:
  training_metrics:
    buffer_size: 1000  # Smaller buffer (less memory)
```

**Disable Features:**

```yaml
frontend:
  decision_boundary:
    enabled: false  # Skip boundary computation
```

---

### Export and Logging

**Training Logs:**

```bash
logs/training.log  # All training metrics
```

**System Logs:**

```bash
logs/system.log    # Application events
```

**UI Interaction Logs:**

```bash
logs/ui.log        # User interactions
```

**Log Rotation:**

- Daily rotation at midnight
- 30-day retention
- Automatic compression

---

## Getting Help

### Documentation

- [README.md](../README.md) - Quick start guide
- [API_REFERENCE.md](api/API_REFERENCE.md) - Complete API documentation
- [DEVELOPMENT_ROADMAP.md](../notes/history/DEVELOPMENT_ROADMAP.md) - Planned features
- [CHANGELOG.md](../CHANGELOG.md) - Release history

### Support

- **Issues:** Report bugs via GitHub Issues
- **Questions:** Check AGENTS.md for developer guidelines
- **Email:** <paul.calnon@example.com> (replace with actual contact)

### Version Information

The running version comes from the installed package metadata and is shown by `GET /v1/health`
and the **About** tab (both read the same source); the release history is in `CHANGELOG.md`.

**Python:** 3.11+ (`requires-python` in `pyproject.toml`)
**License:** MIT

---

## Appendix

### Keyboard Shortcuts

```markdown
*(Future feature - currently not implemented)*
```

### Glossary

- **CasCor** - Cascade Correlation neural network architecture
- **Epoch** - One complete pass through the training dataset
- **Cascade Unit** - Hidden unit added dynamically during training
- **Hidden depth** - View filter on the Network Topology tab; keeps the first `K` cascade units. Slider `0` and slider-at-max both mean "all" (no filter).
- **Decision Boundary** - Regions where network changes classification
- **WebSocket** - Bidirectional real-time communication protocol
- **FastAPI** - Modern Python web framework for APIs
- **Dash** - Python framework for interactive web dashboards
- **Node selection** - Topology click or box/lasso highlight. Clicking empty canvas does not clear (F-CANOPY-046). Click the selected node again, or (after canopy#573) use **Clear selection**.

### System Requirements

**Minimum:**

- Python 3.12+
- 2GB RAM
- Modern web browser (Chrome, Firefox, Safari, Edge)

**Recommended:**

- Python 3.13+
- 4GB RAM
- 2+ CPU cores
- Fast network connection (for remote access)

---

## End of User Manual
