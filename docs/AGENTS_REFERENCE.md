# AGENTS Reference — juniper-canopy

**Project**: juniper-canopy — Real-Time Monitoring Dashboard for Juniper
**Author**: Paul Calnon
**License**: MIT License
**Last Updated**: 2026-09-05

Reference material relocated **verbatim** out of `AGENTS.md` under the shared-session-memory plan
(juniper-ml plan §P5 step e). `AGENTS.md` is loaded into every session; this file is read on demand.
Nothing here was rewritten — each section carries a provenance line naming where it came from.

**Hazards are deliberately NOT here.** Directives whose *non-application destroys work* stay
resident in [`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate), because a
pointer only helps an agent that already knows to look.

---

## Table of Contents

- [Architecture Reference](#architecture-reference)
- [Event-loop I/O discipline (X7)](#event-loop-io-discipline-x7)
- [Hierarchy Depth Filter (CAN-020)](#hierarchy-depth-filter-can-020)
- [Topology Node Selection (F-CANOPY-046)](#topology-node-selection-f-canopy-046)
- [Plotly PNG Export (F-CANOPY-047)](#plotly-png-export-f-canopy-047)
- [Configuration Reference](#configuration-reference)
- [API and WebSocket Contract Reference](#api-and-websocket-contract-reference)
- [Cascor status cache (X7 slice 1c)](#cascor-status-cache-x7-slice-1c)
- [Further Reading](#further-reading)

---

## Architecture Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Directory Structure

```bash
juniper_canopy/
├── conf/                         # Configuration & infrastructure
│   ├── app_config.yaml           # Main application config (YAML layer)
│   ├── layouts/                  # Dashboard layout definitions
│   │   └── metrics_layouts.json  # Metrics panel layout config
│   ├── conda_environment.yaml    # Conda env spec
│   ├── conda_environment_ci.yaml # CI-specific conda env
│   ├── requirements.txt          # Pip dependencies
│   ├── requirements_ci.txt       # CI pip dependencies
│   ├── Dockerfile                # Container image for Juniper Canopy
│   ├── docker-compose.yaml       # Local stack (app + services like Redis)
│   ├── logging_config.yaml       # Logging configuration
│   ├── logging_colors.conf       # Color output configuration
│   ├── init.conf                 # Shared shell init for utility scripts
│   └── ... (60+ shell/logging/env configs)
├── data/                         # Datasets for training/testing
├── docs/                         # Reference & subsystem documentation
│   ├── api/                      # API schema and reference docs
│   ├── cascor/                   # CasCor backend integration docs
│   ├── cassandra/                # Cassandra integration docs
│   ├── ci_cd/                    # CI/CD pipeline documentation
│   ├── demo/                     # Demo mode behavior & usage
│   ├── deployment/               # Kubernetes deployment plan
│   ├── history/                  # Archived/superseded documentation
│   ├── redis/                    # Redis/cache integration docs
│   ├── testing/                  # Testing guides and advanced scenarios
│   └── *.md                      # Quick start, environment setup, reference, etc.
├── images/                       # Generated images/screenshots
├── logs/                         # Log files (runtime)
├── notes/                        # Development notes and implementation details
│   ├── analysis/                 # Technical analyses
│   ├── development/              # Dev roadmaps and phase work
│   ├── fixes/                    # Bug fix plans and reports
│   ├── history/                  # Historical analyses and audits
│   ├── integration/              # Integration phase analysis (phases 0-5)
│   ├── mcp/                      # MCP server setup guides
│   ├── pull_requests/            # PR descriptions
│   ├── releases/                 # Release notes (v0.14.0+)
│   ├── research/                 # Research proposals
│   └── templates/                # Issue, PR, release note templates
├── reports/                      # Test coverage and CI reports
├── scripts/                      # Service management scripts
│   ├── generate_dep_docs.sh      # Dependency documentation generator
│   ├── juniper-canopy.service    # Systemd service file
│   └── juniper-ctl               # Service control utility
├── src/                          # Source code
│   ├── backend/                  # CasCor backend integration & adapters
│   │   ├── __init__.py           # Backend factory (create_backend)
│   │   ├── protocol.py           # BackendProtocol typing interface
│   │   ├── demo_backend.py       # DemoBackend (wraps DemoMode)
│   │   ├── service_backend.py    # ServiceBackend (wraps CascorServiceAdapter)
│   │   ├── cascor_service_adapter.py # juniper-cascor-client wrapper
│   │   ├── circuit_breaker.py    # Fault tolerance
│   │   ├── cassandra_client.py   # Optional Cassandra integration
│   │   ├── redis_client.py       # Optional Redis caching
│   │   ├── data_adapter.py       # Data normalization
│   │   ├── training_monitor.py   # Metrics collection (TrainingState)
│   │   ├── training_state_machine.py # FSM for training control
│   │   ├── state_sync.py         # State synchronization
│   │   └── statistics.py         # Statistics module
│   ├── communication/            # WebSocket management & protocol
│   │   └── websocket_manager.py  # WebSocket connection and broadcast management
│   ├── frontend/                 # Dash dashboard components & callbacks
│   │   ├── dashboard_manager.py  # DashboardManager orchestrator
│   │   ├── base_component.py     # BaseComponent for UI modules
│   │   ├── callback_context.py   # Callback context utilities
│   │   ├── tooltips.py           # UI tooltips
│   │   └── components/           # Individual UI panel components
│   │       ├── about_panel.py
│   │       ├── candidate_metrics_panel.py
│   │       ├── cassandra_panel.py
│   │       ├── dataset_plotter.py
│   │       ├── decision_boundary.py
│   │       ├── hdf5_snapshots_panel.py
│   │       ├── metrics_panel.py
│   │       ├── network_visualizer.py
│   │       ├── parameters_panel.py
│   │       ├── redis_panel.py
│   │       ├── training_metrics.py
│   │       ├── tutorial_panel.py
│   │       └── worker_panel.py
│   ├── logger/                   # Logging system
│   │   └── logger.py             # Structured JSON/text logging
│   ├── tests/                    # Test suite
│   │   ├── unit/                 # Unit tests (fast, no external deps)
│   │   │   ├── backend/          # Backend component unit tests
│   │   │   └── frontend/         # Frontend component unit tests
│   │   ├── integration/          # Integration tests (DB, files, backend)
│   │   │   └── backend/          # Backend integration tests
│   │   ├── regression/           # Regression tests for fixed bugs
│   │   ├── performance/          # Performance/benchmark tests
│   │   ├── fixtures/             # Additional test fixtures
│   │   ├── mocks/                # Mock implementations
│   │   ├── data/                 # Test data generators
│   │   └── helpers/              # Test utility functions
│   ├── main.py                   # FastAPI + Dash application entrypoint
│   ├── settings.py               # Pydantic BaseSettings configuration (primary)
│   ├── config_manager.py         # Legacy YAML-based configuration (deprecated)
│   ├── canopy_constants.py       # Central constants (see "Constants Management")
│   ├── demo_mode.py              # Demo mode simulation
│   ├── discovery.py              # Auto-discovery of cascor instances
│   ├── health.py                 # Health check probes (/v1/health/*)
│   ├── middleware.py             # Security, rate limiting, CSP headers
│   ├── observability.py          # Sentry, Prometheus, request ID middleware
│   ├── security.py               # API key authentication, rate limiting
│   └── secrets_util.py           # Environment secret management
├── util/                         # Utility scripts (bash, invoked via ./demo, etc.)
│   └── verification/             # Verification helper scripts
├── .env.dev                      # Development environment variables
├── .env.example                  # Example environment template
├── .env.prod                     # Production environment variables
├── .mcp.json                     # MCP server configuration
├── AGENTS.md                     # This file
├── CHANGELOG.md                  # Chronological change history
├── CLAUDE.md -> AGENTS.md        # Symlink for Claude Code
├── Dockerfile                    # Root-level container image
├── LICENSE                       # MIT License
├── README.md                     # Project overview
├── conftest.py                   # Root pytest config (adds src/ to path)
├── demo                          # Symlink -> util/juniper_canopy-demo.bash
├── pyproject.toml                # Python project config (black, isort, pytest, coverage)
├── requirements.lock             # Locked dependencies
└── try                           # Symlink -> util/juniper_canopy.bash
```

### Key Components

1. **FastAPI Backend** (`src/main.py`)
   - RESTful API endpoints (30+ routes)
   - WebSocket endpoints for real-time communication (`/ws/training`, `/ws/control`, `/ws`)
   - Dash app integration via WSGI middleware (`a2wsgi`)
   - Async lifespan manager for startup/shutdown orchestration

2. **Pydantic Settings** (`src/settings.py`)
   - Primary configuration via `JUNIPER_CANOPY_*` env vars
   - Typed, validated settings with nested model hierarchy
   - Legacy `CASCOR_*` fallback with deprecation warnings
   - See [Configuration Management](../AGENTS.md#configuration-management) for details

3. **Dash Dashboard** (`src/frontend/dashboard_manager.py`)
   - `DashboardManager` orchestrates all UI components
   - 13 specialized panel components in `frontend/components/`
   - Interactive real-time plotting via Plotly/Dash callbacks
   - **Training counter semantics (Step / Epoch / Iteration / Hidden Units).** The
     header, Network Info panel and metrics tiles render cascor's training counters,
     whose meanings are the **C2b contract** (single source of truth: juniper-cascor
     [`docs/api/JUNIPER_CASCOR_API_REFERENCE.md`](https://github.com/pcalnon/juniper-cascor/blob/main/docs/api/JUNIPER_CASCOR_API_REFERENCE.md)
     — "Counter semantics (C2b)"; reconciled in cascor#400). Do not conflate them:
     `current_epoch`/`current_step` = completed **training steps** (one initial output
     pass + one per growth iteration), rendered "Step" — **not** an inner epoch;
     `grow_iteration`/`grow_max` = the true growth **"Iteration"** (vs `max_iterations`),
     distinct from the hidden-unit count; `hidden_units`/`max_hidden_units` = installed
     units vs capacity; `output_epoch`/`candidate_epoch` (+ `*_total_epochs`) = the
     phase-qualified within-pass **"Epoch"** (resets to 0 at each phase entry by design);
     `max_epochs` = the **derived display budget** (`output_epochs + min(max_iterations,
     max_hidden_units) * (candidate_epochs + output_epochs)`), surfaced as the Parameters
     panel's "Maximum Total Epochs" — **not** an `Epoch: X / Y` fraction against the step
     counter (different units). `DashboardManager._counter_displays()` is the shared
     mapping helper; regressions live in `src/tests/unit/frontend/test_n6_counter_semantics.py`.

4. **Backend Protocol & Factory** (`src/backend/protocol.py`, `src/backend/__init__.py`)
   - `BackendProtocol` defines the typing interface for all backends
   - Factory function `create_backend()` selects DemoBackend or ServiceBackend based on settings
   - Dependency injection pattern for testability

5. **Service Backend** (`src/backend/service_backend.py`, `src/backend/cascor_service_adapter.py`)
   - `ServiceBackend` wraps `CascorServiceAdapter` for production use
   - `CascorServiceAdapter` uses `juniper-cascor-client` for REST/WebSocket communication
   - Circuit breaker pattern for fault tolerance (`src/backend/circuit_breaker.py`)
   - State synchronization with remote cascor (`src/backend/state_sync.py`)

6. **Demo Backend** (`src/backend/demo_backend.py`, `src/demo_mode.py`)
   - `DemoBackend` wraps `DemoMode` for offline development
   - Simulated CasCor training loop with realistic metrics
   - Thread-safe operation via locks and events

7. **Training State Machine** (`src/backend/training_state_machine.py`, `src/backend/training_monitor.py`)
   - FSM for training command validation (START, STOP, PAUSE, RESUME, RESET)
   - `TrainingPhase` enum: IDLE, OUTPUT, CANDIDATE, INFERENCE
   - `TrainingStatus` enum: STOPPED, STARTED, PAUSED, COMPLETED, FAILED
   - Thread-safe global state tracking via `TrainingState`

8. **WebSocket Manager** (`src/communication/websocket_manager.py`)
   - Connection management with heartbeat
   - Thread-safe broadcasting via `broadcast_from_thread()`
   - Message builder functions for standardized schemas

9. **Health & Observability** (`src/health.py`, `src/observability.py`)
   - Health check probes: `/v1/health`, `/v1/health/live`, `/v1/health/ready`
   - Dependency probing (JuniperData, CasCor availability)
   - Sentry integration, Prometheus metrics, request ID middleware

10. **Infrastructure Clients** (`src/backend/redis_client.py`, `src/backend/cassandra_client.py`)
    - Optional Redis caching (soft-fail if not installed)
    - Optional Cassandra time-series storage (soft-fail if not installed)
    - Status endpoints for monitoring

11. **Security & Middleware** (`src/security.py`, `src/middleware.py`)
    - API key authentication
    - Rate limiting
    - CSP headers, CORS configuration

12. **Constants Module** (`src/canopy_constants.py`)
    - Centralized application constants
    - Type-safe configuration values
    - Training parameters, UI settings, server config

---

## Hierarchy Depth Filter (CAN-020)

Operator surface: the Network Topology tab's **Hidden depth** slider
(`network-visualizer-depth-slider`). Developer contract below. User-facing
copy lives in [`USER_MANUAL.md` § Network Topology Tab](USER_MANUAL.md#network-topology-tab).

### Intent

CasCor cascade order *is* the hierarchy: `hidden_0` was added first,
`hidden_N-1` most recently. The slider keeps the first `K` hidden units
(and any edge that touches a dropped unit) so a deep cascade can be read
one prefix at a time. It is a **view filter** — it does not change the
backend network.

The control is hidden until `topology.hidden_units >= 1`. Slider `max`
tracks the live hidden-unit count clientside; a user-picked `K` persists
across `cascade_add` as long as it is still in range, otherwise it snaps
to the new max (show all).

### Filter contract

`NetworkVisualizer._apply_hierarchy_filter(topology, depth, n_hidden_total)`
is the oracle. It never mutates the input dict (that payload is a Dash
store other callbacks also read). No-op arms return the original
reference and label `"all"`:

| `depth` / `n_hidden_total` | Graph | Label |
| --- | --- | --- |
| `depth is None` | unchanged | `"all"` |
| `depth <= 0` | unchanged | `"all"` |
| `depth >= n_hidden_total` | unchanged | `"all"` |
| `n_hidden_total == 0` | unchanged | `"all"` |
| `0 < depth < n_hidden_total` | `hidden_units` capped at `depth`; drop any edge whose `from`/`to` is `hidden_K` with `K >= depth` | `"{depth} of {n_hidden_total}"` |

Unparseable node ids (`hidden_x`) are kept — the filter cannot decide.

**`0` means "no filter", not "show zero units."** The slider ships
`min=0, max=0, value=0`. Treating rest-state `0` as a real depth would
blank the graph. The same rest state is why a label that only special-
cases `v === nHidden` reads `"0 of 40"` while all 40 units are drawn.

The filter runs inside `update_network_graph` **before** `compute_hash`,
so a depth change invalidates the figure cache. That callback is the
starvation-prone rebuild (measured **1.5–31 s**; F-CANOPY-037 / -039 /
-043). Do not add `-depth-label.children` as a ninth Output of it —
the number under the thumb would lag the drag by seconds, and two of
the four return paths are empty-figure exits with no meaningful label.

### Label wiring (F-CANOPY-042)

Two defects, one finding id.

**Defect A — State vs Input.** The label *was* the fourth Output of the
clientside slider-bounds sync. That callback's only Input is
`-topology-store.data`; `-depth-slider.value` rode as **State**. A
State is read when something *else* fires, so moving the slider
recomputed nothing. Since canopy#542 identity-suppressed the topology
store, at idle the label never updated at all.

The obvious repair is structurally unavailable: adding
`Input(-depth-slider, "value")` to that callback makes one
component-property both an Input and an Output of a single callback,
which Dash rejects at registration as a circular dependency. The
bounds-sync callback **must** keep writing `max` and `value` (it bumps
`max` on grow and snaps an out-of-range pick). Therefore the label
cannot live there.

**Defect B — two meanings of `0`.** The filter's `depth <= 0` arm is
`"all"`. The old clientside rule was `(v === nHidden) ? "all" : v + " of " + nHidden`.
On a loaded 40-unit network the control *read* `"0 of 40"` while all 40
units were displayed, before anyone touched anything. Fixing the wiring
alone would not have fixed this.

**The repair (canopy#570, on `main`):** a second clientside
callback owns `-depth-label.children` with Inputs
`[-depth-slider.value, -topology-store.data]` — both operands of the
filter, because a grow event changes the denominator with no user
action. The JavaScript guard is a condition-for-condition
transliteration of `_apply_hierarchy_filter`. The bounds-sync callback
returns three elements (`max`, `value`, container `style`). #570 merged,
so Defect A and Defect B are fixed on `main`.

### Dual definition — change one, change both

`_apply_hierarchy_filter` still *returns* the label. The rebuild
discards it on purpose so the readout is not stuck behind the 1.5–31 s
paint. That return value stays the definition the clientside rule
transliterates. A label that says `"0 of 40"` while the filter returns
the unfiltered topology is exactly F-CANOPY-042. Edit the Python guard
and the JavaScript guard in the same change.

### Tests

On `main`:

```bash
cd src
pytest tests/unit/test_network_visualizer.py -k "Hierarchy or hierarchy or depth" -v
```

`TestHierarchyDepthFilter` drives the Python oracle directly (None / 0 /
at-total / above-total / keep-3 / drop-edges / no-mutate /
malformed-id). `TestHierarchyDepthSliderWiring` is source-level only —
it does not execute the clientside function.

The #570 suite (`src/tests/unit/frontend/test_f042_depth_filter_label.py`)
asserts wiring against `app._callback_list` after a
real `register_callbacks`, executes the registered JavaScript under
`node` over a 48-case grid with `_apply_hierarchy_filter` as the oracle,
and pins that no callback has `-depth-slider.value` as both Input and
Output. Do not replace that shape with a test that re-types the
production expression and asserts against its own copy — that class let
F-CANOPY-041b and F-CANOPY-045 ship green.

E2E rows M-TOPOLOGY-06 / M-TOPOLOGY-07 live in juniper-ml. The old
M-TOPOLOGY-06 predicate was `label == want OR counts["hidden"] == want`
and passed on the counts branch while the label stayed `"0 of 40"`.
M-TOPOLOGY-07 recorded the label but scored `display` alone.

### Pitfalls

- Do not merge the label back into the bounds-sync callback. Dash will
  refuse the registration (or a future "simplification" will silently
  restore Defect A).
- Do not route the label through `update_network_graph`. Correct by
  construction, unusable under the thumb.
- Do not treat slider `value=0` as "show zero hidden units."
- Do not mutate the topology dict inside the filter.
- Count writers by grepping the store / component id, not by reading
  the handler you happened to open (`allow_duplicate` and a split
  clientside callback are both easy to miss). Same lesson as the
  `metrics-panel-metrics-store` hazard in `AGENTS.md`.

---

## Topology Node Selection (F-CANOPY-046)

Operator surface: the Network Topology tab's selection panel
(`network-visualizer-selection-info`) and the `-selected-nodes` store.
Developer contract below. User-facing copy lives in
[`USER_MANUAL.md` § Network Topology Tab](USER_MANUAL.md#network-topology-tab).

Click or box/lasso a node to inspect it. The store is view state — it
does not change the backend network. `update_network_graph` takes
`-selected-nodes.data` as a real **Input** and draws a highlight overlay
(`_create_selection_highlight`). Any write to that store, identical or
not, rebuilds the figure (measured **1.5–31 s**; F-CANOPY-037 / -039 /
-043). canopy#542 identity-suppressed the *topology* store; this store
has no such guard.

### How a click becomes a node (F-CANOPY-044 / F-CANOPY-045)

`handle_node_selection` (`prevent_initial_call=True`) has two Inputs on
`main`: `-graph.clickData` and `-graph.selectedData`.

**F-CANOPY-044.** Edges are drawn *to* node centres, so a click aimed at
a node resolves to an EDGE trace (measured 0 of 7 clicks landing on a
node trace). Edge points have no `text`. The handler reads
`point.get("text") or point.get("customdata")`. The edge traces carry
the endpoint node labels in `customdata`, so a click on an edge vertex
still identifies the node there. Reordering traces so the node series
come first does **not** break plotly's pick — do not "fix" this by
shuffling `data` order.

**F-CANOPY-045.** Layer is the first word of that same label
(`Input` / `Hidden` / `Output`), not `curveNumber`. The old
`layer_names[min(curve_number, 4)]` table is correct only if the node
traces are curves 2–4. With one trace per connection they sit at
~1888–1890, so every node reported `"Output"`.

`node_id` is `text.lower().replace(" ", "_")` (`"Hidden 0"` →
`hidden_0`).

### What actually clears a selection

| Gesture | Result on `main` |
| --- | --- |
| Click the already-selected node again | Clears. The toggle branch returns `[]`. |
| Click any member of a box/lasso set | Clears the **whole** set (same toggle: `node_id in current_selection` → `[]`). |
| Click empty canvas | **Nothing.** Plotly emits `plotly_click` only on a point hit. `clickData` does not change, the callback never runs. Measured: 7 empty-canvas clicks, 0 events. |
| Box / lasso (`select2d` / `lasso2d`) | Selects. Panel lists up to 5 ids. Box points use `text` only (no `customdata` fallback). |

The panel *used to say* *"(Click again or elsewhere to deselect)"* after a
click and *"(Click elsewhere to deselect)"* after a box select. The
"again" half is true. The "elsewhere" half was never implemented — only
described, which is why canopy#573 removed it. On `main` the click hint
reads *"(Click again to deselect)"* and the box branch carries **no**
hint at all.

### Store write cost

The fall-through at the bottom of `handle_node_selection` *used to write*
`[]` unconditionally. Because `-selected-nodes` is an Input of
`update_network_graph`, a click that resolved to nothing (or a clear of
an already-empty store) paid the full 1.5–31 s rebuild. canopy#573 added
the `if not current_selection: return dash.no_update` guard. Assert
`is dash.no_update`, **not** `== []` — equality passes against the broken
write, so an `== []` test cannot tell the repair from the defect.

### The repair (canopy#573, on `main`)

A **"Clear selection"** button (`-clear-selection`) is wired as a third
**Input** (the click *is* the trigger) and a fourth Output that sets
`display` to `inline-block` only while something is selected — no dead
button on an empty panel. The click hint keeps *"(Click again to
deselect)"* and drops *"or elsewhere"*. The box branch drops its hint
entirely; the visible button carries the affordance.

Both clear paths return `dash.no_update` on all four Outputs when
`current_selection` is already empty.

A clientside listener on the graph container would literally satisfy
the old sentence and was rejected: it races plotly's own event path,
and this is the callback family this arc has repeatedly starved.

### Tests

On `main`:

```bash
cd src
pytest tests/unit/frontend/test_f044_node_click_selection.py -v
```

Every test in that file reaches the real registered callback or the
real trace builder. Do not replace it with a test that re-types
`layer_names[min(curve_number, 4)]` and asserts against its own copy —
that class let F-CANOPY-045 ship green while every node read
`"Output"`.

`test_network_visualizer_callbacks.py` `TestHandleNodeSelectionCallback`
still drives a *re-implementation* (`_simulate_handle_node_selection`)
for several cases; treat those as historical, not as the contract.

The #573 suite (`src/tests/unit/frontend/test_f046_clear_selection.py`)
reaches the real callback, builds its argument list
from the live signature, and asserts `is dash.no_update` on the empty-
clear path. Adding an Input and an Output changes arity: three existing
files invoke the callback for real
(`test_f044_node_click_selection.py`,
`test_network_visualizer_callbacks.py`,
`tests/regression/test_dark_mode_info_panels.py`). The last two locate
it by Output key, not by the function name — a grep for
`handle_node_selection` misses them.

E2E row M-TOPOLOGY-12 lives in juniper-ml. On a build with no clear
control it scores **BLOCKED**, not FAIL. The empty-canvas click is
still recorded (and still produces zero `plotly_click` events) as the
evidence for why the contract changed.

- Do not add a container-level click listener to "make elsewhere work."
  It races plotly and starves this callback family (F-CANOPY-037 / -039
  / -043).
- Do not write `[]` over an already-empty `-selected-nodes`. Return
  `dash.no_update`.
- Do not derive layer from `curveNumber`. The label is the contract.
- Do not require `point.text` without the `customdata` fallback. Most
  node-aimed clicks land on an edge.
- When changing this callback's arity, grep the **Output key**
  (`-selected-nodes.data`), not the handler name.
- Count writers by grepping the store id. `-selected-nodes` has one
  writer today; an `allow_duplicate` second writer would be invisible
  from the handler you happened to open.

## Plotly PNG Export (F-CANOPY-047)

Operator surface: the Network Topology modebar camera
(`dcc.Graph` `toImageButtonOptions` in
[`network_visualizer.py`](../src/frontend/components/network_visualizer.py)).
The policy that lets that button produce a file is
`SecurityConstants.DEFAULT_CSP_POLICY`, served on every response by
[`SecurityHeadersMiddleware`](../src/middleware.py).

User-facing copy lives in

The camera rasterises the figure as **SVG → Blob → `<img>` → canvas →
`toDataURL`**. That `<img>` load is a `blob:` URL. Without `blob:` in
`img-src`, the browser refuses it, plotly's promise rejects with a bare
`[object Event]`, no `<a download>` is clicked, and the operator sees
a correctly configured button that does nothing. The console is the
only signal:

```text
Loading the image 'blob:http://127.0.0.1:8051/...' violates the
following Content Security Policy directive: "img-src 'self' data:".
```

SVG export from the same menu still works — serialisation never hits
`img-src`. The defect is the scheme, not the figure.

### Current policy (on `main`, canopy#565)

`SecurityConstants.DEFAULT_CSP_POLICY` is:

```text
default-src 'self';
style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
script-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
frame-ancestors 'none'
```

`main.py` mounts `SecurityHeadersMiddleware()` with no override.
`middleware._DEFAULT_CSP` is an alias of that constant — pin both, or a
test that only reads the constant cannot fail for what the browser
gets.

There is **no** `JUNIPER_CANOPY_*` setting for CSP. Editing
`DEFAULT_CSP_POLICY` is the production path.

### Two `img-src` schemes, two consumers

| Scheme | Consumer | What breaks without it |
| --- | --- | --- |
| `data:` | Bootstrap form-control SVG icons | Sidebar / form controls fail to render |
| `blob:` | Plotly PNG rasteriser (F-CANOPY-047) | Modebar camera silently produces no file |

These are **not** interchangeable. Replacing `data:` with `blob:`
fixes plotly and breaks every Bootstrap form control. Adding `blob:`
without keeping `data:` is the same class. The two regression files
exist so a future edit that satisfies one while breaking the other
fails a test named after the thing it broke:

- [`test_csp_bootstrap_cdn.py`](../src/tests/regression/test_csp_bootstrap_cdn.py)
  pins `data:` (and the Bootstrap CDN on `style-src`).
- [`test_csp_plotly_image_export.py`](../src/tests/regression/test_csp_plotly_image_export.py)
  pins `blob:`. `test_middleware_coverage.py` still only asserts
  `data:` — that is why the dedicated file exists.

### Scope: `blob:` is img-only

`blob:` URLs are minted by this page's own scripts and are opaque
origins a third party cannot forge. Allowing them for **IMG** does not
admit external content. That case does **not** extend to executing
`blob:` script.

Do not add `blob:` to `script-src` or `default-src`. Do not open
`img-src` with `*` or `http:`. The plotly file asserts all four.

### UI contract

`network_visualizer.py` sets `toImageButtonOptions` to
`format: png`, `scale: 2`. The rebuild path (`_dynamic_graph_config`)
also stamps `filename: canopy_network_<YYYYmmdd>_<HHMMSS>`. The
layout-time graph omits the filename (plotly's default applies until
the first rebuild). The button is present and correctly configured
even when CSP blocks the rasteriser — that is why the failure is
silent.

Measured live (juniper-ml
`util/ad-hoc/2026-09-03_modebar_download_probe.py`) against the
pre-fix policy: topology PNG scale=2 failed in 4.4 s with
`[object Event]`; scale=1 failed the same way; SVG export wrote
1,211,031 bytes; a 10×10 SVG failed via `blob:` and succeeded via
`data:` on the same page.

A control that itself rasterises through a `blob:` URL proves
nothing: it fails for the same reason as the subject.

pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v

- Do not replace `data:` with `blob:`. Add, do not swap.
- Do not put `blob:` on `script-src` or `default-src`.
- Do not "fix" a silent camera by widening `img-src` to `*`.
- Do not treat a green `test_middleware_coverage.py` as evidence
  plotly export works — that file does not pin `blob:`.
- Do not introduce a CSP env override without teaching both tests
  to read the value that actually ships on the response.

## Configuration Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Configuration Hierarchy

The juniper_canopy application uses a three-level configuration hierarchy (highest to lowest priority):

1. **Pydantic BaseSettings** (`src/settings.py`) - `JUNIPER_CANOPY_*` environment variables with typed validation
2. **YAML Configuration** (`conf/app_config.yaml`) - Deployment-specific settings (legacy)
3. **Constants Module** (`src/canopy_constants.py`) - Application defaults

> **Note**: The previous `CASCOR_*` environment variable prefix is deprecated but still supported with deprecation warnings. All new code should use `JUNIPER_CANOPY_*`.

### Pydantic Settings (Primary)

The `Settings` class in `src/settings.py` provides typed, validated configuration:

```python
from settings import get_settings

settings = get_settings()
host = settings.server.host       # "127.0.0.1"
port = settings.server.port       # 8050
demo = settings.demo_mode         # False
```

### Environment Variable Overrides

All configuration values can be overridden via environment variables with the `JUNIPER_CANOPY_` prefix. Nested settings use double-underscore (`__`) as delimiter.

#### Server Configuration

```bash
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0      # Server bind address (default: 127.0.0.1)
export JUNIPER_CANOPY_SERVER__PORT=8051          # Server port (default: 8050)
export JUNIPER_CANOPY_SERVER__DEBUG=true         # Debug mode (default: false)
```

#### Training Parameters

```bash
export JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=300          # Default epochs (default: 1000000)
export JUNIPER_CANOPY_TRAINING__LEARNING_RATE__DEFAULT=0.02  # Learning rate (default: 0.01)
export JUNIPER_CANOPY_TRAINING__HIDDEN_UNITS__DEFAULT=500    # Max hidden units (default: 1000)
```

#### Backend Integration

```bash
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/cascor  # CasCor backend path (default: ../juniper-cascor)
export JUNIPER_CANOPY_CASCOR_SERVICE_URL=http://localhost:8200  # CasCor service URL
export JUNIPER_CANOPY_JUNIPER_DATA_URL=http://localhost:8100    # JuniperData service URL
```

#### CasCor Auto-Discovery

```bash
export JUNIPER_CANOPY_CASCOR_DISCOVERY__ENABLED=true          # Enable auto-discovery (default: true)
export JUNIPER_CANOPY_CASCOR_DISCOVERY__HOST=localhost         # Discovery host (default: localhost)
export JUNIPER_CANOPY_CASCOR_DISCOVERY__PORTS=[8200]           # Ports to probe (default: [8200])
export JUNIPER_CANOPY_CASCOR_DISCOVERY__TIMEOUT_SECONDS=2.0   # Probe timeout (default: 2.0)
```

#### WebSocket Configuration

```bash
export JUNIPER_CANOPY_WEBSOCKET__MAX_CONNECTIONS=100      # Max concurrent connections (default: 50)
export JUNIPER_CANOPY_WEBSOCKET__HEARTBEAT_INTERVAL=60    # Heartbeat interval in seconds (default: 30)
export JUNIPER_CANOPY_WEBSOCKET__RECONNECT_ATTEMPTS=10    # Reconnection attempts (default: 5)
export JUNIPER_CANOPY_WEBSOCKET__RECONNECT_DELAY=5        # Delay between reconnects (default: 2)
```

#### Demo Mode

```bash
export JUNIPER_CANOPY_DEMO_MODE=true             # Enable demo mode (default: false)
export JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL=0.5   # Simulation step interval (default: 1.0)
export JUNIPER_CANOPY_DEMO_CASCADE_EVERY=40      # Add hidden unit every N epochs (default: 30)
```

#### Logging & Observability

```bash
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG             # Log level (default: INFO)
export JUNIPER_CANOPY_LOG_FORMAT=json             # Log format: text or json (default: text)
export JUNIPER_CANOPY_SENTRY_DSN=https://...      # Sentry DSN for error tracking (default: unset)
export JUNIPER_CANOPY_METRICS_ENABLED=true        # Enable Prometheus metrics (default: false)
```

#### Rate Limiting & CORS

```bash
export JUNIPER_CANOPY_RATE_LIMIT_ENABLED=true                  # Enable rate limiting (default: false)
export JUNIPER_CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE=120       # Requests per minute (default: 60)
export JUNIPER_CANOPY_CORS_ORIGINS='["http://localhost:3000"]'  # Allowed CORS origins (default: [])
```

#### Shared / Cross-Service Variables

```bash
export JUNIPER_DATA_URL=http://localhost:8100       # JuniperData URL (shared, no prefix)
export JUNIPER_DATA_API_KEY=your-api-key            # JuniperData API key
export JUNIPER_CASCOR_API_KEY=your-api-key          # CasCor API key
export CANOPY_API_KEY=your-api-key                  # Canopy API key (disables /docs if set)
```

### Legacy CASCOR_* Environment Variables

The following legacy variables are supported with deprecation warnings:

| Legacy Variable | New Variable | Notes |
|----------------|-------------|-------|
| `CASCOR_DEMO_MODE` | `JUNIPER_CANOPY_DEMO_MODE` | Boolean flag |
| `CASCOR_BACKEND_PATH` | `JUNIPER_CANOPY_BACKEND_PATH` | Path to cascor |
| `CASCOR_SERVICE_URL` | `JUNIPER_CANOPY_CASCOR_SERVICE_URL` | Service URL |

If both legacy and new variables are set, the new `JUNIPER_CANOPY_*` variable takes precedence.

### YAML Configuration (Secondary)

Configuration file location: `conf/app_config.yaml`

The YAML configuration is a secondary layer used by the legacy `ConfigManager`. New settings should be added to `settings.py` instead.

### Using Configuration in Code

```python
from settings import get_settings
from canopy_constants import ServerConstants

# Primary: use Pydantic Settings
settings = get_settings()
host = settings.server.host       # Typed, validated
port = settings.server.port

# Constants: for values not in Settings
default_host = ServerConstants.DEFAULT_HOST
```

### Configuration Best Practices

1. **Use Pydantic Settings**: Add new config to `settings.py`, not `config_manager.py`
2. **Validate via type system**: Pydantic handles validation automatically
3. **Use the `JUNIPER_CANOPY_` prefix**: All new env vars must use this prefix
4. **Double-underscore for nesting**: `JUNIPER_CANOPY_SERVER__PORT=8051`
5. **Document all overrides**: Comment why environment variables are being set

### Testing Configuration

```bash
# Run configuration tests
cd src
pytest tests/unit/test_config_refactoring.py -v          # Unit tests
pytest tests/integration/test_config_integration.py -v   # Integration tests

# Test with environment variable overrides
export JUNIPER_CANOPY_TRAINING__EPOCHS__DEFAULT=500
export JUNIPER_CANOPY_SERVER__PORT=8051
./demo
# Verify dashboard shows updated settings

# Validate Settings loading
python -c "from settings import get_settings; s = get_settings(); print(f'port={s.server.port}')"
```

### Configuration Troubleshooting

**Problem**: Environment variable not taking effect

**Solution**: Check variable name and nesting delimiter

```bash
# Correct (new prefix with double-underscore nesting)
export JUNIPER_CANOPY_SERVER__PORT=8051

# Incorrect (single underscore — not nested)
export JUNIPER_CANOPY_SERVER_PORT=8051

# Legacy (still works but deprecated)
export CASCOR_SERVER_PORT=8051
```

**Problem**: Configuration value seems wrong

**Solution**: Check which settings layer is being used

```bash
# Inspect resolved settings
python -c "from settings import get_settings; s = get_settings(); print(s.model_dump())"
```

**Problem**: YAML configuration not loading

**Solution**: Verify YAML syntax and file location

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"
```

---

## API and WebSocket Contract Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### REST API Endpoints

All REST endpoints defined in [src/main.py](../src/main.py) and [src/health.py](../src/health.py). Document request/response schemas in code docstrings.

#### Health & Status

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root redirect |
| `GET` | `/health` | Legacy health check |
| `GET` | `/api/health` | Legacy health check |
| `GET` | `/v1/health` | Standard health check |
| `GET` | `/v1/health/live` | Liveness probe |
| `GET` | `/v1/health/ready` | Readiness probe (checks JuniperData, CasCor) |

#### Training Control

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/train/start` | Start training |
| `POST` | `/api/train/pause` | Pause training |
| `POST` | `/api/train/resume` | Resume training |
| `POST` | `/api/train/stop` | Stop training |
| `POST` | `/api/train/reset` | Reset training state |
| `GET` | `/api/train/status` | Get training status |
| `POST` | `/api/set_params` | Apply training parameters |

#### Metrics & State

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/state` | Current training state |
| `GET` | `/api/status` | Training status |
| `GET` | `/api/metrics` | Current training metrics |
| `GET` | `/api/metrics/history` | Historical metrics |
| `GET` | `/api/network/stats` | Network statistics |

#### Network & Topology

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/topology` | Network topology |
| `GET` | `/api/topology/raw` | Raw topology data |
| `GET` | `/api/dataset` | Dataset information |
| `POST` | `/api/dataset/generate` | Generate dataset |
| `GET` | `/api/decision_boundary` | Decision boundary visualization |
| `GET` | `/api/statistics` | Network statistics |

#### Snapshots (HDF5)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/snapshots` | List snapshots |
| `GET` | `/api/v1/snapshots/history` | Snapshot history |
| `GET` | `/api/v1/snapshots/{id}` | Get specific snapshot |
| `POST` | `/api/v1/snapshots` | Create snapshot |
| `POST` | `/api/v1/snapshots/{id}/restore` | Restore snapshot |

#### Metrics Layouts

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/metrics/layouts` | List metric layouts |
| `GET` | `/api/v1/metrics/layouts/{name}` | Get layout |
| `POST` | `/api/v1/metrics/layouts` | Create layout |
| `DELETE` | `/api/v1/metrics/layouts/{name}` | Delete layout |

#### Infrastructure (Redis/Cassandra)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/redis/status` | Redis status |
| `GET` | `/api/v1/redis/metrics` | Redis metrics |
| `GET` | `/api/v1/cassandra/status` | Cassandra status |
| `GET` | `/api/v1/cassandra/metrics` | Cassandra metrics |
| `GET` | `/api/v1/workers/stats` | Worker statistics |
| `GET` | `/api/v1/workers/list` | Worker list |

#### Remote Workers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/remote/status` | Remote worker status |
| `POST` | `/api/remote/connect` | Connect to remote manager |
| `POST` | `/api/remote/start_workers` | Start workers |
| `POST` | `/api/remote/stop_workers` | Stop workers |
| `POST` | `/api/remote/disconnect` | Disconnect |

### WebSocket Channels

**Channels:**

| Path | Description |
|------|-------------|
| `/ws/training` | Stream metrics and state updates in real-time |
| `/ws/control` | Send commands (start, stop, pause, resume, reset) |
| `/ws` | Legacy WebSocket endpoint |

**Message Format:**

```python
{
    "type": "metrics" | "state" | "topology" | "event" | "control_ack",
    "timestamp": 1234567890.123,  # Unix timestamp in seconds
    "data": {...}  # Payload varies by type
}
```

**Threading Safety:**

```python
# From background thread -> async WebSocket
websocket_manager.broadcast_from_thread(message)

# From async context
await websocket_manager.broadcast(message)
```

**Backward Compatibility Rule:**

- Do not change existing payload keys without versioning
- Add new keys as optional
- Update dashboard consumers before changing contracts
- Add integration tests for all contract changes

---

## Code Style Reference

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### File Headers

All Python files should include the standard project header:

```python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       <version>
# File Name:     <filename>.py
# File Path:     <Project>/<Sub-Project>/<Application>/<Source Directory Path>/
#
# Created Date:  <date created>
# Last Modified: <date last changed>
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     <High level description of the current script>
#
#####################################################################################################################################################################################################
# Notes:
#     <Additional information about the script>
#
#####################################################################################################################################################################################################
# References:
#     <External information sources or documentation relevant to the script>
#
#####################################################################################################################################################################################################
# TODO :
#     <List of pending tasks or improvements for the script>
#
#####################################################################################################################################################################################################
# COMPLETED:
#     <List of completed tasks or features for the script>
#
#####################################################################################################################################################################################################
```

### Naming Conventions

- **Classes:** PascalCase (e.g., `DemoMode`, `WebSocketManager`)
- **Functions/Methods:** snake_case (e.g., `get_metrics_history`, `broadcast_from_thread`)
- **Constants:** _UPPER_SNAKE_CASE (e.g., `_MAX_EPOCHS`, `_DEFAULT_PORT`)
- **Private attributes:** Prefix with double underscore (e.g., `self.__private_data`)
- **Protected attributes:** Prefix with single underscore (e.g., `self._lock`)

### Metric Naming Standard

- Use snake_case for all metric names
- Prefix with `train_` or `val_` where relevant (e.g., `train_loss`, `val_loss`, `train_accuracy`, `val_accuracy`)
- Standard metrics: `epoch`, `step`, `loss`, `accuracy`, `learning_rate`
- Follow consistent naming across backend and frontend for interoperability

### Blocking Rules

- **No global mutable state without locks** - All shared state must use `threading.Lock()` for protection
- **Any long-lived collections must be size-bounded** - Use `maxlen` for deques, limit history buffers to prevent memory leaks
- **No synchronous network I/O inside `async def`** — canopy is a single-worker uvicorn; one blocking `requests` call stalls `/v1/health/live`. See [Event-loop I/O discipline (X7)](#event-loop-io-discipline-x7).

### Thread Safety

When writing concurrent code:

```python
import threading

class ThreadSafeClass:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def update_state(self, value):
        """Thread-safe state update."""
        with self._lock:
            self.state = value

    def get_state(self):
        """Thread-safe state retrieval."""
        with self._lock:
            return self.state
```

### Async/Thread Communication

For calling async code from threads:

```python
import asyncio

# In async context (FastAPI startup)
event_loop = asyncio.get_running_loop()
websocket_manager.set_event_loop(event_loop)

# From background thread
websocket_manager.broadcast_from_thread(message)
```

For calling **synchronous** network I/O from an `async def` handler, hop off the loop. Do not
invoke the client on the coroutine:

```python
# Correct — the request thread blocks, the event loop does not
return await asyncio.to_thread(backend.get_status)

# Wrong — single-worker uvicorn: this stalls every route, including /v1/health/live
return backend.get_status()
```

See [Event-loop I/O discipline (X7)](#event-loop-io-discipline-x7) for the gate, the callgraph
instrument, and the constraints this idiom does **not** satisfy.

### Error Handling

```python
def robust_function():
    """Handle errors appropriately."""
    try:
        # Main logic
        result = some_operation()
    except ImportError:
        # Expected errors - silent or debug logging
        logger.debug("Optional module not available")
    except SpecificException as e:
        # Known errors - warning logging
        logger.warning(f"Known issue: {type(e).__name__}: {e}")
        return default_value
    except Exception as e:
        # Unexpected errors - error logging
        logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        raise
```

---

## Event-loop I/O discipline (X7)

Operator runbook for the X7 outage class. Not a P5 relocation — added 2026-09-04 after
slice 1b merged (`#566`) and slice 1a opened (`#567`). The resident one-line hazard lives in
[`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate).

### What X7 is

Canopy is a **single-worker** uvicorn. A synchronous, retrying `requests` call inside an
`async def` handler holds the only event loop, so **every** route stalls — including
`/v1/health/live`, which touches no backend. Measured end-to-end:

| Condition | Observed latency |
| --- | --- |
| Healthy cascor | 5.7 ms |
| Cascor stopped (`ECONNREFUSED`) | 3.0 s (retry backoff sleep; closed by slice 1b) |
| Cascor hung | **123.12 s** (`timeout × (retries + 1) + backoff`) |
| Recovery after cascor returns | 5.1 ms, no canopy restart |

This is a recurrence of SEC-F20: the first fix shipped a comment and no test.

### Slices

| Slice | Role | Status |
| --- | --- | --- |
| **1b** | Bound per-call cost (`timeout=30`, `retries=0`) instead of inheriting the client defaults (`timeout=30`, `retries=3`) | Merged `#566` |
| **1a** | Move every remaining synchronous network call off the event loop | `#567` — this is the slice that **closes X7** |
| **1c** | Status cache + classifier | Landed (`#578`) |
| **1d** | Admission control (constraint C4) | Landed (`#581`) |

Slice 1a ships **bare** `asyncio.to_thread`. That is acceptable only because 1b already
bounds per-call cost. **C4 (bounded concurrency) is deferred to 1d**, not satisfied here.

### Correct idiom

Two shapes the committed gate recognises as offloaded:

```python
# Bare-attribute offload — the backend call is an Attribute, never a Call
return await asyncio.to_thread(backend.get_status)

# Named closure handed to to_thread
def _fetch():
    return backend.get_status()
return await asyncio.to_thread(_fetch)
```

Do **not** write `return backend.get_status()` inside `async def`. Do **not** "fix" one
site by adding a module-global exemption for the expression `backend.get_status` — that
was the unsound draft that would have certified a partial fix as complete (offloading
one site hid every other, including the three health endpoints). Exemption is
**site-local** only: calls inside a closure that is itself handed to an offloader.

### Client budget (slice 1b, on `main`)

`BackendConstants` names the budget the adapter must pass explicitly:

- `CASCOR_CLIENT_TIMEOUT_SECONDS = 30.0` — kept at the client default; canopy's slowest
  legitimate operation (`/api/train/restart`) budgets 30 s.
- `CASCOR_CLIENT_RETRIES = 0` — the load-bearing half. urllib3 backoff is pure `sleep`
  on the calling thread. Measured 3.005 s → 0.002 s per `ECONNREFUSED`. Canopy re-polls
  on its own interval, so client-level retries buy nothing and duplicate non-idempotent
  verbs (`RETRY_ALLOWED_METHODS` includes POST and DELETE).

Pinned by `src/tests/regression/test_x7_client_budget.py` (T-B1 refused-call milliseconds;
T-B2 a 503 is attempted once). Dropping the keywords silently restores the inherited
`retries=3` defaults.

### Structural gate (slice 1a)

`src/tests/regression/test_x7_off_loop_discipline.py` asserts the count is **zero**. It is
a gate, not a sample.

- **Reads `main.py` only.** A green result is not proof that 1a is complete.
- **Provenance resolution, not name matching.** The bare name `client` is bound to the
  cascor client, redis, cassandra, *and* an `httpx.AsyncClient`. Name-matching is the
  same flaw that makes `ruff --select ASYNC` report "All checks passed!" against these
  sites: ruff matches a hardcoded list of callee names and cannot see
  `backend.get_status()`.
- **Closure-aware.** A naive lexical scan reports the correct idiom as unguarded.
- **Transitive `HELPER` bucket.** A bare call to a module-level sync function whose body
  reaches the network (`_extract_meta_params`, `_seed_training_state`) is the same defect.
  `census()` accepts an optional AST so the rule is proved to *fire* against a synthetic
  dirty module, not only proved quiet against a file that happens to be clean.
- **`UNRESOLVED` fails.** An unaudited receiver is how a check goes quietly wrong.

Verified in-process (not offloaded): `backend.get_synced_state`,
`backend.set_state_update_callback`, `backend._demo.get_network`,
`backend._demo.get_current_state`. Offloaded despite being in-memory today:
`get_stream_health` (uniformity — an exemption would need re-verifying on every edit).

Four sites outside `main.py` are invisible to this gate and were found by the callgraph
below: `CascorServiceAdapter.connect` → `is_alive()`, `_relay_loop` →
`extract_network_topology()` (measured **123 s blocked per 183 s with no user present**),
and `ServiceBackend.initialize` → `attach_to_existing()` / `CascorStateSync.sync()`.
`initialize()` is on the **request path**: `_swap_backend` awaits it when the operator
changes model at runtime.

### Behavioural tests (T-A2 / T-A3 / T-A4)

`src/tests/regression/test_x7_loop_responsiveness.py` proves the property the structure
is supposed to buy: **while an upstream is slow, canopy still answers**.

| Id | Assertion |
| --- | --- |
| **T-A2** | 3 concurrent `GET /api/status` against a bounded 2.0 s stub; `GET /v1/health/live` answers in **< 500 ms** |
| **T-A3** | Four vacuity guards: probe sample non-empty; every driver waited the stub's bound; the driver reached the backend (counted at the stub); the identical harness **fails** against a deliberately un-offloaded control app |
| **T-A4** | 8 threads × 4 uniquely-tagged requests against a local echo server: no cross-talk, one shared `Session`, headers unchanged afterwards |

Not marked `slow` despite exceeding that marker's 1 s threshold: the coverage gate runs
`-m "not slow"`, so the marker would remove the only behavioural check X7 has. Bound
total runtime ~5 s.

**T-A4 corrects constraint C5 on evidence.** C5 called for a `threading.local()` session
because a shared `requests.Session` must not be used from multiple threads, and 1a
removes the accidental protection the blocked loop provided (concurrency was pinned at
1). `JuniperCascorClient` mutates session state **only in `__init__`**; `_request` passes
method/url/json/params/timeout as arguments. What is shared is the `HTTPAdapter`'s
urllib3 pool, which is thread-safe and is why `pool_maxsize` exists. A thread-local
session would discard keep-alive across the executor. If per-request session mutation is
ever added upstream, T-A4 fails and C5's original remedy becomes the right one.

### Adapter callgraph (outside the gate)

```bash
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py --all   # include adjudicated
```

A taint-propagating call graph over canopy plus `juniper-cascor-client` and
`juniper-data-client`. Exit status is always 0: this is an **instrument**, not a gate.
**Run it when touching the adapter.**

Constraints:

- Requires a sibling `juniper-cascor-client` checkout. The script walks up from the repo
  (including worktrees) and **exits** if the sibling is missing. A missing corpus is the
  worst failure: every adapter method looks pure and the census prints a confident `0`.
- Resolution is by bare method name and over-reports (`close()` collapses). Read every
  hit; the in-file `ADJUDICATED` table records verdicts already reached.
- Its first draft rooted receiver chains at `self`, seeded nothing, and printed `0` over
  a file with 52 known sites. That bug and the reason are recorded in the script.

### Operator commands

```bash
# Slice 1b — client budget (on main)
cd src && pytest tests/regression/test_x7_client_budget.py -v

# Slice 1a — structural gate + behavioural tests (landed with #567)
cd src && pytest tests/regression/test_x7_off_loop_discipline.py tests/regression/test_x7_loop_responsiveness.py -v

# Adapter-wide census (needs sibling client checkouts)
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py
```

### Pitfalls

- `ruff --select ASYNC` (the CI-blocking "Async-route audit (BUG-JD-10 class)" hook)
  cannot see this class. A green ruff run is not evidence the loop is safe.
- Do not mark the X7 behavioural tests `slow`. Coverage would drop them.
- Do not treat a green `main.py` gate as "1a done" after editing
  `cascor_service_adapter.py` or `service_backend.py`.
- Do not add a module-global expression exemption. Site-local only.
- `/v1/health/live` is the canary (`{"status": "alive"}`). `/v1/health` and `/api/status`
  reach the backend and must be offloaded; `/v1/health/ready` probes dependencies via
  async `probe_dependency`.
- Timing a responsiveness test from *inside* the coroutine measures only the coroutine.
  Clock from request **issue** time, and create driver tasks before probes.

Design of record (juniper-ml, revision 4):
`notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md`.

---

## Cascor status cache (X7 slice 1c)

Operator runbook for the incoming status cache (`#578`). Slice 1a (on `main` as `#567`)
already moved every blocking call off the event loop, so canopy answers HTTP under a dead
upstream. It did **not** reduce the number of upstream calls, and it did **not** make an
unreachable backend legible. 1c does both, and is droppable without reopening X7.

The module is `src/backend/status_cache.py`, landed with `#578`.

The resident one-line hazard lives in
[`AGENTS.md` § Hazards](../AGENTS.md#hazards-resident--do-not-relocate). Off-loop
discipline (slices 1a / 1b) is a **different** gap; its runbook landed via
the docs consolidation `#583` (`#568` was closed superseded).

### What 1c buys

| Constraint | Meaning |
| --- | --- |
| **C2** | One background task polls cascor; every browser tab polling `/api/status` costs **zero** upstream calls. |
| **C6** | An unknown backend is never presented as a fresh negative. With no OK ever seen, the body omits `is_training` rather than passing through the adapter's `{"is_training": False, "error": …}`. |
| **C7** | Health surfaces (`/v1/health`, `/api/health`, `/v1/health/ready` `details`) gain additive `backend_status` / `backend_status_stale` / `backend_status_age_seconds` in **service mode only**. Status codes are unchanged: an upstream outage stays 200 / degraded. |
| **C9** | Every non-fresh read carries `stale` and `age_seconds`. |

`/v1/health/ready` is otherwise left alone. `is_training_active()` keeps its `bool`
contract — widening it to a tri-state was measured to open all five 409 interlocks.
Staleness is reported **beside** the boolean, not smuggled into it.

Demo and recurrence backends get **no** cache: they answer `get_status()` from memory, so
there is no upstream call to amortise.

### Intervals (derived, not chosen)

| Constant | Value | Why |
| --- | --- | --- |
| `REFRESH_INTERVAL_SECONDS` | 1.0 s | Tightest consumer is the 15 s healthcheck with a 5 s budget; the dashboard fast lane is also 1.0 s. |
| `STALE_AFTER_SECONDS` | 5.0 s | The probe budget. A value older than a probe's deadline is not fresh *to that probe*. |
| `UNKNOWN_AFTER_SECONDS` | 30.0 s | The longest probe interval. Past this with no attempt, the cache admits it has no recent knowledge. |

**Single-flight is structural, not enforced.** The loop awaits its fetch and *then*
sleeps, so a second tick cannot begin while one is in flight — there is no lock to get
wrong. The same ordering is **self-limiting**: a 30 s timeout yields a 1/31 Hz poll, not
a pile of 1 Hz calls. That is why there is **no backoff** (design OQ-X2): backoff would
only delay recovery detection, which is what the status bar exists to show.

### Classifier

`classify(raw)` is pure and total — every input, including `None` / `[]` / a bare
string, lands in exactly one class. An exception here would kill the refresher and freeze
the last verdict (machinery-fails-green).

The predicate is canopy's own `CascorServiceAdapter.is_cascor_nested` (positive detection
of cascor's nested structure). An earlier draft keyed on `is_training`, which appears
**only on the failure path**, and misclassified 7 of 20 measured healthy shapes as
UNREACHABLE.

| Class | When | Status-bar label |
| --- | --- | --- |
| `ok` | Nested cascor shape, no truthy `error` | Payload (`Running` / `Stopped` / …) |
| `unreachable` | Reached an answer, and the answer is bad — including a **half-dead 200** (dict, no `error`, not cascor-shaped) | **Unreachable** |
| `indeterminate` | Call was **skipped** (`"circuit open"` in `error`) | **Unknown** |

`INDETERMINATE` is not a hedge. An open breaker means the tick observed nothing.
Reporting UNREACHABLE would claim evidence that was never gathered.

### Dedicated breaker

The refresher calls `adapter.get_training_status_for_refresh()`, **not**
`get_training_status()`. The shared `_cb` fronts five call sites; five failing
`get_network_data()` calls would otherwise freeze this cache for the full 60 s recovery
timeout **against a healthy upstream**. The dedicated breaker is named
`BackendConstants.STATUS_CIRCUIT_BREAKER_NAME` (`"cascor-status"`). Same threshold /
recovery as the shared breaker; a second *instance*, not a second name for the first
one (`CircuitBreaker` keeps state per instance).

### Route the class, not the payload

`dashboard_manager` renders "Unreachable" from a truthy `error` (the PR `#340` branch).
On a half-dead 200 that branch does not fire and the elif chain renders **"Stopped"** —
indistinguishable from a healthy idle backend. So the cache publishes `status_class` and
the UI renders the class. Mutation-checked: removing the class routing makes T-C2 fail
with `'Stopped' == 'Unreachable'`.

Every non-OK `/api/status` body still carries a truthy `error` so a UI that has not been
taught about `status_class` keeps the `#340` branch. The half-dead 200, which has no
error of its own, gets one synthesised.

### Two guards the design implies

- **A refresher that dies** would leave the last verdict frozen. `current_class()` ages
  out on the last **attempt**, not the last success. Past `UNKNOWN_AFTER_SECONDS` with no
  attempt, the honest answer is INDETERMINATE.
- **C6 with no OK ever seen.** The body omits `is_training`. Passing through the
  adapter's `{"is_training": False, "error": …}` is how a cache invents "not training"
  during a live run whose status call merely failed.

A raising fetch is UNREACHABLE, not a reason to stop polling. A raising Prometheus sink
is logged and swallowed — observability must not kill the refresher it observes.

### `/api/status` envelope (service mode)

```json
{
  "is_training": true,
  "is_running": true,
  "status_class": "ok",
  "stale": false,
  "age_seconds": 0.2
}
```

Never-OK body (C6): `status_class`, `stale: true`, `age_seconds: null`, a truthy
`error`, and **no** `is_training`.

### Health extras (C7)

Additive, service-mode only:

| Field | Source |
| --- | --- |
| `backend_status` | `status_class` (`ok` / `unreachable` / `indeterminate`) |
| `backend_status_stale` | `stale` |
| `backend_status_age_seconds` | `age_seconds` |

### Prometheus (registered, not yet observable)

`juniper_canopy_backend_status_class{status_class=…}` is one gauge per class (0 or 1),
so an alert reads `{status_class="unreachable"} == 1` without knowing an ordinal.
`JUNIPER_CANOPY_METRICS_ENABLED` defaults `false` and gates both the middleware and the
`/metrics` mount; `/metrics` also sits behind the trusted-IP allowlist. Enabling that
pair is a later PR. Design §5.6 binds acceptance to the **status bar** for exactly this
reason.

### Tests (landed with `#578`)

`src/tests/regression/test_x7_status_cache.py`.

| Id | Assertion |
| --- | --- |
| **T-C1** | Table-driven classifier census over observed shapes, plus a vacuity guard that the table exercises all three classes |
| **T-C2** | Half-dead 200 → "Unreachable", plus a vacuity guard that the same body *without* the class still renders "Stopped" |
| **T-C3** | Dedicated breaker: five failing `get_network_data()` calls open the shared breaker and leave the status breaker closed |
| **T-C4** | Staleness contract, never-OK omits `is_training`, dead refresher ages out, single-flight peak is 1, prompt/idempotent stop, raising sink cannot kill the loop |

cd src && pytest tests/regression/test_x7_status_cache.py -v

- Do not hand the status bar a raw payload. That re-creates PR `#340` on a half-dead 200.
- Do not share `_cb` with the refresher. Isolation is T-C3.
- Do not invent `is_training: False` on a never-OK cache. That is C6.
- Do not age out on last success. A dead refresher would stay green forever.
- Do not widen `is_training_active()` to a tri-state. Report staleness beside it.
- Do not claim the Prometheus gauge is watched. It is registered; it is not yet a channel.
- Slice **1d** (admission control) is where C4 — bounded concurrency — actually gets
  satisfied. 1a and 1c both still ship bare offload.

Design of record (juniper-ml):
`notes/JUNIPER_2026-09-03_JUNIPER-CANOPY_X7-EVENT-LOOP-BLOCKING-REMEDIATION-DESIGN.md` §5.3 / §5.6.

## Further Reading

- [`AGENTS.md`](../AGENTS.md) — the resident agent guide this material was relocated from.
- [`docs/REFERENCE.md`](REFERENCE.md) — index of technical reference documents.
- [`docs/DOCUMENTATION_OVERVIEW.md`](DOCUMENTATION_OVERVIEW.md) — documentation navigation, and the
  authoring/maintenance rules relocated in the preceding cut.
