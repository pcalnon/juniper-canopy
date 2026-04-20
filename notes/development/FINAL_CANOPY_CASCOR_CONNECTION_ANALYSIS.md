# FINAL Canopy–CasCor Connection Analysis

- **Version**: 1.0.0
- **Date**: 2026-03-28
- **Author**: Final synthesis generated from Phase 5 Proposal A (`7f73219c-1557-4135-ab44-ef053d4c4097`) and Phase 5 Proposal B (`8b7d1ee8-a24d-4e2a-bfd6-8df44d7ed326`)
- **Status**: Final synthesis complete — implementation reference
- **Scope**: juniper-canopy, juniper-cascor, juniper-cascor-client
- **Source Material**:
  - Phase 5 Proposal A: `PHASE_5_CANOPY_CASCOR_CONNECTION_ANALYSIS_7f73219c-1557-4135-ab44-ef053d4c4097.md`
  - Phase 5 Proposal B: `PHASE_5_CANOPY_CASCOR_CONNECTION_ANALYSIS_8b7d1ee8-a24d-4e2a-bfd6-8df44d7ed326.md`
  - 4 Phase 4 comprehensive analyses
  - 7 Phase 3 independent proposals
  - Phase 1 and Phase 2 development plans and root cause analyses
  - Phase 0 original analysis documents
- **Final Resolution Rules**:
  - All unique issues from both Phase 5 proposals are preserved
  - Proposal B numbering (`P5-RC-*`) is canonical
  - Uppercase status normalization gap retained as HIGH latent bug (P5-RC-03) per directive
  - Proposal A's evidence that current CasCor sends title-case is preserved and incorporated
- **Code Validation**: All line numbers and code patterns independently verified against current codebase HEAD

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Synthesis Methodology and Governing Resolutions](#2-synthesis-methodology-and-governing-resolutions)
3. [Phase 1 / Phase 2 Assessment and Unanimous Findings](#3-phase-1--phase-2-assessment-and-unanimous-findings)
4. [Unified Issue Registry](#4-unified-issue-registry)
5. [Detailed Issue Analysis](#5-detailed-issue-analysis)
6. [Cross-Proposal Agreement Matrices](#6-cross-proposal-agreement-matrices)
7. [Disagreements and Final Resolutions](#7-disagreements-and-final-resolutions)
8. [Architectural Root Cause Analysis and Dependency Graph](#8-architectural-root-cause-analysis-and-dependency-graph)
9. [False Positives and Retractions](#9-false-positives-and-retractions)
10. [Verified Working Paths](#10-verified-working-paths)
11. [Consolidated Fix Recommendations](#11-consolidated-fix-recommendations)
12. [Implementation Priority and Ordering](#12-implementation-priority-and-ordering)
13. [Risk Assessment](#13-risk-assessment)
14. [Verification Plan](#14-verification-plan)
15. [Files Requiring Modification](#15-files-requiring-modification)
16. [Post-Synthesis Validation Notes](#16-post-synthesis-validation-notes)
17. [Appendix A: Phase 4 Proposal Assessment](#appendix-a-phase-4-proposal-assessment)
18. [Appendix B: Complete Phase 3 → Phase 5 → Final Issue Lineage](#appendix-b-complete-phase-3--phase-5--final-issue-lineage)
19. [Appendix C: Evidence Inventory](#appendix-c-evidence-inventory)
20. [Appendix D: Document Lineage](#appendix-d-document-lineage)

---

## 1. Executive Summary

### 1.1 Primary Finding

The juniper-canopy dashboard fails to display metrics and topology from an external juniper-cascor instance because **the service-mode data contract does not match the dashboard's actual consumption contract**.

- **Phase 1's 14 ResponseEnvelope fixes are correctly implemented**
- The critical miss in Phase 1 was **not validating the normalized service output against the dashboard's nested format**
- The dashboard was built against **demo mode** as the working reference
- Demo mode emits **nested metrics** (`metrics.loss`, `metrics.accuracy`) and **graph-oriented topology** (`input_units`, `connections`)
- Service mode emits **flat metrics** (`train_loss`, `train_accuracy`) and **weight-oriented topology passthrough** (`input_size`, `hidden_units: [...]`)

### 1.2 Final Synthesis Outcome

This final synthesis tracks **20 entries total**:

- **18 primary numbered root causes**: `P5-RC-01` through `P5-RC-18`
- **1 supplemental low-severity sub-issue**: `P5-RC-12b`
- **1 known limitation**: `KL-1`

Severity distribution:

| Category | Count |
|---|---|
| **CRITICAL** (display blockers) | 2 |
| **HIGH** (latent compatibility) | 1 |
| **MODERATE** | 8 |
| **LOW** | 5 |
| **INFO** | 1 |
| **SYSTEMIC** | 1 |
| Known Limitation | 1 |
| Supplemental sub-issue | 1 |
| False positives retracted | 3 |

### 1.3 Two Critical Display Blockers

| ID | Severity | Summary | Display Blocker |
|---|---|---|---|
| **P5-RC-01** | **CRITICAL** | Metrics format mismatch: flat service metrics vs nested dashboard contract | **Yes** |
| **P5-RC-02** | **CRITICAL** | Network topology mismatch: weight-oriented CasCor topology vs graph-oriented visualizer contract | **Yes** |

**Practical bottom line**:

- Fixing **P5-RC-01** alone restores metrics charts and current metric displays
- Fixing **P5-RC-01 + P5-RC-02** restores core dashboard usability
- All other issues affect data freshness, correctness, deployment portability, or architectural quality but do not prevent the dashboard from displaying data

### 1.4 Final Resolution of the Main Divergence

**Divergence**: Whether the uppercase status normalization gap should be removed (Proposal A) or retained as a latent bug (Proposal B).

**Final resolution**: Retain as **P5-RC-03 HIGH (latent)**.

Rationale:

- **Proposal A was correct** that current CasCor WebSocket broadcasts use **title-case** values like `"Started"` and `"Output"` (verified: `lifecycle/manager.py:111`), so current CasCor does not actively trigger the bug
- **Proposal B was correct** to keep the issue active, because:
  - The relay path at `cascor_service_adapter.py:222` has no `.lower()` call, while the sync path at `state_sync.py:70` does — asymmetric protection
  - `FakeCascorClient` already uses uppercase in tests, triggering the bug in test paths
  - Additional backend objects (other than the current CasCor backend) will be attached to the canopy application in the near future, and these new backends may pass uppercase values
  - The fix is trivial (one-line change or centralized case-insensitive normalization) and low-risk

This makes the bug:

- **Latent for current CasCor** (title-case is already handled)
- **Active as a compatibility hazard for future backends and tests**
- **Worth fixing now** as a defensive measure

---

## 2. Synthesis Methodology and Governing Resolutions

### 2.1 Methodology

This document merges both Phase 5 proposals using these rules:

1. **Keep all unique issues from both proposals** — no issue identified by either proposal is dropped
2. **Prefer the more rigorous or more complete description** where both proposals agree on an issue
3. **Preserve Proposal A evidence** where it improves accuracy (e.g., title-case validation for P5-RC-03)
4. **Preserve Proposal B numbering and granularity** as the canonical scheme
5. **Where A subsumed or removed an issue that B kept**, retain the issue if the directive or technical evidence warrants it
6. **Separate "same root cause, second code path" issues** when doing so prevents implementation omissions
7. **Treat demo mode as the canonical working contract** — it is the target format for all service-mode transformations
8. **All line number references independently verified** against current codebase HEAD

### 2.2 Canonical Numbering

The final document uses Proposal B's numbering:

- `P5-RC-01` through `P5-RC-18`
- `P5-RC-12b` preserved as a distinct sub-issue
- `KL-1` preserved as a known limitation

### 2.3 Proposal Attribution Legend

In tables throughout this document:

| Symbol | Meaning |
|---|---|
| ✓ | Correctly identified with materially correct classification |
| P | Partially correct (identified symptom/evidence, not final classification) |
| S | Subsumed into another issue, not separated |
| — | Not identified separately |

- **Proposal A** = `7f73219c-1557-4135-ab44-ef053d4c4097`
- **Proposal B** = `8b7d1ee8-a24d-4e2a-bfd6-8df44d7ed326`

### 2.4 Repositories Examined

| Repository | Key Files Analyzed |
|---|---|
| juniper-canopy | `cascor_service_adapter.py`, `service_backend.py`, `state_sync.py`, `main.py`, `metrics_panel.py`, `network_visualizer.py`, `dashboard_manager.py`, `demo_mode.py`, `demo_backend.py`, `protocol.py`, `data_adapter.py`, `dataset_plotter.py`, `training_monitor.py` |
| juniper-cascor | `api/lifecycle/manager.py`, `api/lifecycle/monitor.py`, `api/lifecycle/state_machine.py`, `api/models/training.py`, `api/models/network.py`, `cascade_correlation_config.py` |
| juniper-cascor-client | `client.py`, `ws_client.py`, `testing/fake_client.py`, `testing/scenarios.py` |

---

## 3. Phase 1 / Phase 2 Assessment and Unanimous Findings

### 3.1 Phase 1: Correctly Implemented but Incompletely Validated

Both Phase 5 proposals unanimously agree:

1. All **14 Phase 1 fixes** (FIX-1 through FIX-13, plus FIX-SYS) are correctly implemented
2. ResponseEnvelope unwrapping is working
3. Falsy-value preservation (epoch=0, loss=0.0) is working
4. Canopy↔CasCor field normalization was improved correctly
5. The critical oversight was **stopping validation too early**

The failure point was not the Phase 1 code itself. It was the **Phase 1 contract assumption**.

Phase 1 normalized CasCor metrics to a flat structure:

```python
{"epoch": 5, "train_loss": 0.45, "train_accuracy": 0.82, "val_loss": 0.60, "val_accuracy": 0.65, "hidden_units": 3, "phase": "output", "timestamp": "..."}
```

But the dashboard reads a nested structure:

```python
{"epoch": 5, "metrics": {"loss": 0.45, "accuracy": 0.82, "val_loss": 0.60, "val_accuracy": 0.65}, "network_topology": {"hidden_units": 3}, "phase": "output", "timestamp": "..."}
```

The Phase 1 "Canonical Internal Contract" (Section 6.2) defined flat keys by analyzing the normalization boundary (CasCor → canopy adapter). **It was never validated against the dashboard's actual input format.** The dashboard was built against demo mode's nested format — a different contract entirely.

The status bar worked because it reads flat keys, creating false confidence that the flat contract was sufficient.

### 3.2 Phase 2: Correct but Too Narrow

Both proposals agree Phase 2 correctly identified:

| Phase 2 Finding | Status |
|---|---|
| RC-1: Metrics format mismatch | **Correct** — primary blocker |
| RC-2: Relay callback omits fields | **Correct** — impact overstated for status bar |
| RC-3: Dashboard ignores WebSocket | **Correct** — low priority |

**Phase 2 gaps**: Did not examine topology path, parameter mapping, state sync normalization, deployment portability, cross-repo bugs, or architectural contract enforcement. These gaps account for 12+ additional root causes discovered in Phase 3.

### 3.3 Unanimous Findings Preserved in Final Document

Both Phase 5 proposals unanimously agree, and this final document adopts without change:

1. **P5-RC-01 is the primary blocker** — all 7 Phase 3 proposals, all 4 Phase 4 proposals, both Phase 5 proposals
2. **P5-RC-02 is the secondary blocker** — identified by Phase 3 v2 and v4, confirmed by all Phase 4 and Phase 5 proposals
3. **All Phase 1 fixes were implemented correctly** — ResponseEnvelope unwrapping, field normalization, falsy-value preservation
4. **Phase 1's canonical flat contract was never validated against dashboard reality**
5. **The correct fix pattern is `_normalize_metric()` followed by `_to_dashboard_metric()`**
6. **Demo mode is the reference implementation** — its output format is what the dashboard expects
7. **Status bar correctness created false confidence** because it reads a different contract (flat keys via fresh REST calls)

---

## 4. Unified Issue Registry

### 4.1 Final Registry

| ID | Severity | Status | Summary | Proposal A | Proposal B |
|---|---|---|---|:---:|:---:|
| **P5-RC-01** | **CRITICAL** | Active | Metrics format mismatch: flat service output vs nested dashboard contract | ✓ | ✓ |
| **P5-RC-02** | **CRITICAL** | Active | Topology format mismatch: weight-oriented vs graph-oriented | ✓ | ✓ |
| **P5-RC-03** | **HIGH** | Latent | Uppercase status normalization gap in relay path | P | ✓ |
| **P5-RC-04** | MODERATE | Active | WebSocket relay state callback only forwards `status` + `phase` | ✓ | ✓ |
| **P5-RC-05** | LOW | Architectural choice | Dashboard ignores WebSocket relay, polls via HTTP only | ✓ | ✓ |
| **P5-RC-06** | MODERATE | Active | CasCor `TrainingMonitor.current_phase` never updated after initialization | ✓ | ✓ |
| **P5-RC-07** | MODERATE | Latent (low current impact) | State sync stores metrics history without normalization | ✓ | ✓ |
| **P5-RC-08** | MODERATE | Structural | State sync bypasses adapter normalization by using raw client | — | ✓ |
| **P5-RC-09** | MODERATE | Active (second code path) | `/api/metrics` current snapshot path also produces flat format | S | ✓ |
| **P5-RC-10** | MODERATE | Structural (low current impact) | State sync params stored in raw CasCor namespace, not mapped to Canopy | — | ✓ |
| **P5-RC-11** | MODERATE | Active | Hardcoded `localhost:8050` URLs in MetricsPanel (6 instances) | ✓ | ✓ |
| **P5-RC-12** | LOW | Active | `cn_training_iterations` → `candidate_epochs` mapping is non-functional at runtime | ✓ | ✓ |
| **P5-RC-12b** | LOW | Active (semantic mismatch) | `patience` mapped to `nn_growth_convergence_threshold` is semantically misleading | P | ✓ |
| **P5-RC-13** | LOW | Active | `candidate_learning_rate` is updatable in CasCor but unmapped in Canopy | ✓ | ✓ |
| **P5-RC-14** | LOW | Latent | WebSocket relay broadcasts unnormalized metric payloads | ✓ | ✓ |
| **P5-RC-15** | LOW | Active | Double initialization on fallback-to-demo path | ✓ | ✓ |
| **P5-RC-16** | LOW | Preventive | Phase 1 tests validate flat output, not dashboard compatibility | ✓ | ✓ |
| **P5-RC-17** | INFO | Observation | Dual status normalization paths produce inconsistent representations | ✓ | ✓ |
| **P5-RC-18** | **SYSTEMIC** | Structural | No canonical backend contract across demo and service modes | ✓ | ✓ |
| **KL-1** | Known Limitation | Structural limitation | Dataset scatter plot empty in service mode — CasCor returns metadata only | P | ✓ |

### 4.2 Final Classification Notes

- `P5-RC-09` remains listed separately to avoid missing the `/api/metrics` snapshot path during implementation, even though it shares root cause with `P5-RC-01`
- `P5-RC-08` and `P5-RC-10` remain separate because they identify structural state-sync causes not isolated by Proposal A
- `KL-1` is retained as a known limitation rather than an active bug — requires CasCor API extension or direct juniper-data integration to resolve
- `P5-RC-03` is retained despite current title-case evidence because the final directive requires future-backend compatibility

---

## 5. Detailed Issue Analysis

### P5-RC-01 — Metrics Data Format Mismatch [CRITICAL]

- **Severity**: CRITICAL — Primary display blocker
- **Status**: Active
- **Correctly identified by**: Proposal A, Proposal B
- **Underlying consensus**: Unanimous across all 7 Phase 3 proposals, all 4 Phase 4 proposals, both Phase 5 proposals

#### Description

The service backend's `_normalize_metric()` method (`cascor_service_adapter.py:431-460`) produces metrics with **flat** top-level keys. The dashboard's `MetricsPanel` component (`metrics_panel.py`) reads metrics using **nested** dictionary access patterns. Demo mode (`demo_mode.py:1162-1177`) produces the nested format the dashboard expects. No `_to_dashboard_metric()` transformation function exists in the current codebase.

**Service mode output (flat)**:

```python
{"epoch": 5, "train_loss": 0.45, "train_accuracy": 0.82, "val_loss": 0.6, "val_accuracy": 0.65, "hidden_units": 3, "phase": "output", "timestamp": "..."}
```

**Dashboard expects (nested)**:

```python
{"epoch": 5, "metrics": {"loss": 0.45, "accuracy": 0.82, "val_loss": 0.6, "val_accuracy": 0.65}, "network_topology": {"hidden_units": 3}, "phase": "output", "timestamp": "..."}
```

#### Complete Data Flow (Service Mode — Broken)

```text
Step 1: CasCor TrainingMonitor.on_epoch_end()
        → {epoch, loss, accuracy, validation_loss, validation_accuracy, hidden_units, phase}
Step 2: Wrapped in ResponseEnvelope
Step 3: JuniperCascorClient.get_metrics_history() → returns raw response.json()
Step 4: _ServiceTrainingMonitor.get_recent_metrics() → unwraps envelope → _normalize_metric()
        → FLAT: {epoch, train_loss, train_accuracy, val_loss, val_accuracy, hidden_units, phase}
Step 5: ServiceBackend.get_metrics_history() → passes through unchanged
Step 6: main.py /api/metrics/history → {"history": [flat_dicts]}
Step 7: dashboard_manager → stores flat list in metrics-panel-metrics-store
Step 8: MetricsPanel reads:
        metric.get("metrics", {}).get("loss", 0) → {}.get("loss", 0) → ALWAYS 0
        metric.get("network_topology", {}).get("hidden_units", 0) → ALWAYS 0
```

#### Dashboard Nested-Key Access Locations (verified)

| Line(s) | Access Pattern | Affected Display |
|---|---|---|
| 1091 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit count display |
| 1120 | `.get("metrics", {}).get("loss", 0)` | Current loss display |
| 1121 | `.get("metrics", {}).get("accuracy", 0)` | Current accuracy display |
| 1122 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden units display |
| 1330 | `.get("metrics", {}).get("loss", 0)` | Loss chart data series |
| 1449-1450 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (loss) |
| 1499 | `.get("metrics", {}).get("accuracy", 0)` | Accuracy chart data series |
| 1561-1562 | `.get("network_topology", {}).get("hidden_units", 0)` | Hidden unit markers (accuracy) |

#### Field Name Mapping (Non-Trivial)

The `train_` prefix must be stripped when nesting — `train_loss` becomes `metrics.loss`, not `metrics.train_loss`:

| Flat Key (from `_normalize_metric`) | Required Nested Path (dashboard) | Notes |
|---|---|---|
| `train_loss` | `metrics.loss` | Strip `train_` prefix |
| `train_accuracy` | `metrics.accuracy` | Strip `train_` prefix |
| `val_loss` | `metrics.val_loss` | Same name |
| `val_accuracy` | `metrics.val_accuracy` | Same name |
| `hidden_units` | `network_topology.hidden_units` | Move into nested dict |

#### Impact

- Loss chart: All y-values read as `0` — flat line at zero or empty
- Accuracy chart: All y-values read as `0` — flat line at zero or empty
- Current loss/accuracy displays: "0.0000" / "0.00%" or "--"
- Hidden unit count: Always 0
- Hidden unit addition markers: Never rendered (change detection sees 0→0)

#### Also Affected

`get_current_metrics()` (`cascor_service_adapter.py:86-94`) calls the same `_normalize_metric()`, producing flat format. The `/api/metrics` current snapshot endpoint is affected by the same bug (see P5-RC-09).

#### Why Phase 1 Missed This (Unanimous)

Phase 1's "Canonical Internal Contract" (Section 6.2) was designed by analyzing the normalization boundary (CasCor → canopy adapter). It was never validated against the consumption boundary (canopy backend → dashboard). The status bar reads flat keys and worked correctly, creating false confidence that the flat contract was sufficient. The MetricsPanel was built against demo mode's nested format — a different contract entirely.

#### Recommended Fix (Unanimous)

Add `_to_dashboard_metric()` transformation after `_normalize_metric()`:

```python
@staticmethod
def _to_dashboard_metric(flat: dict) -> dict:
    """Transform flat normalized metric to dashboard's nested format.

    Matches the format produced by DemoMode._emit_training_metrics().
    The dashboard (metrics_panel.py) reads metrics using nested access:
      m.get("metrics", {}).get("loss", 0)
      m.get("network_topology", {}).get("hidden_units", 0)
    """
    return {
        "epoch": flat.get("epoch", 0),
        "metrics": {
            "loss": flat.get("train_loss"),
            "accuracy": flat.get("train_accuracy"),
            "val_loss": flat.get("val_loss"),
            "val_accuracy": flat.get("val_accuracy"),
        },
        "network_topology": {
            "hidden_units": flat.get("hidden_units", 0),
        },
        "phase": flat.get("phase"),
        "timestamp": flat.get("timestamp"),
    }
```

Apply in:

- `_ServiceTrainingMonitor.get_recent_metrics()` — wrap each entry after `_normalize_metric()`
- `_ServiceTrainingMonitor.get_current_metrics()` — wrap result after `_normalize_metric()`

**Advantages**: Single transformation point; dashboard code untouched; demo mode unaffected; each layer independently testable; minimal blast radius.

**Risks**: LOW — `network_topology` will only contain `hidden_units` (missing `input_units`, `output_units` that demo mode includes), but the dashboard only reads `hidden_units` from this sub-dict.

---

### P5-RC-02 — Network Topology Format Mismatch [CRITICAL]

- **Severity**: CRITICAL — Secondary display blocker
- **Status**: Active
- **Correctly identified by**: Proposal A, Proposal B
- **Severity disagreement**: One Phase 4 proposal (P4-C/`cd8254d3`) rated MODERATE; resolved to CRITICAL (see Section 7.2)

#### Description

CasCor's `get_topology()` endpoint (`lifecycle/manager.py:563-585`) returns a **weight-oriented** topology structure. The `NetworkVisualizer` (`network_visualizer.py:83-88, 577-601`) expects a **graph-oriented** structure. The adapter's `extract_network_topology()` (`cascor_service_adapter.py:480-484`) is a raw passthrough — `return self._unwrap_response(self._client.get_topology())` — with no structural transformation.

#### Six Structural Mismatches (verified)

| Aspect | CasCor Returns | NetworkVisualizer Expects | Match |
|---|---|---|---|
| Input count key | `input_size` | `input_units` | **No** |
| Output count key | `output_size` | `output_units` | **No** |
| Hidden units type | Array of `{weights, bias, activation}` objects | Integer count | **No** |
| Connection list | Not present (implicit in weight arrays) | Required: `[{from, to, weight}]` | **No** |
| Node list | Not present | Optional: `[{id, type, label}]` | **No** |
| Weight data | In `hidden_units[].weights` and `output_weights` | Inside `connections[].weight` | **No** |

#### Evidence

**CasCor server** (`manager.py:563-585`):

```python
topology = {
    "input_size": self.network.input_size,
    "output_size": self.network.output_size,
    "hidden_units": [
        {"id": i, "weights": unit["weights"].detach().cpu().tolist(),
         "bias": float(unit["bias"]),
         "activation": unit.get("activation_fn", torch.sigmoid).__name__}
    ],
    "output_weights": ...,
    "output_bias": ...,
}
```

**NetworkVisualizer default** (`network_visualizer.py:83-88`):

```python
self.current_topology = {
    "input_units": 0,      # integer
    "hidden_units": 0,     # integer
    "output_units": 0,     # integer
    "connections": [],     # [{from, to, weight}]
}
```

**Adapter passthrough** (`cascor_service_adapter.py:480-484`):

```python
def extract_network_topology(self):
    try:
        return self._unwrap_response(self._client.get_topology())  # no transformation
    except JuniperCascorClientError:
        return None
```

**Demo backend produces correct format** (`demo_backend.py:129-169`): Returns `input_units`, `output_units`, `hidden_units` (integer), `nodes`, `connections`.

**Validation guard always triggers** (`network_visualizer.py:351`): `topology_data.get("input_units", 0) == 0` — since CasCor returns `input_size`, not `input_units`, this always evaluates to 0, displaying an empty graph.

**Contrast with decision boundary** (from P4-D, citing v2): The `get_decision_boundary()` method at `cascor_service_adapter.py:495-543` correctly transforms CasCor's format (`grid_x`/`grid_y`) to the dashboard's format (`xx`/`yy`/`Z`). The topology path has no equivalent transformation, demonstrating that the pattern of format adaptation exists in the codebase but was not applied to topology.

**Additional finding** (Proposal A): `FakeCascorClient` in `juniper-cascor-client/testing/scenarios.py:248-257` returns a **third** format (graph-oriented with `nodes`/`connections`/`layers` but using `input_size`/`output_size` keys), meaning service-mode integration tests using `FakeCascorClient` would not catch this mismatch either.

#### Impact

- Network graph visualization always shows empty placeholder or errors in service mode
- No nodes or connections rendered
- Demo mode works correctly because `DemoBackend` produces graph-oriented format

#### Recommended Fix (synthesized from both proposals)

Add `_transform_topology()` to `CascorServiceAdapter`:

```python
@staticmethod
def _transform_topology(raw: dict) -> dict:
    """Transform CasCor weight-oriented topology to graph-oriented format.

    Cascade correlation architecture: each hidden unit connects to all inputs
    AND all prior hidden units (cascaded connections).
    """
    if "input_units" in raw:
        return raw  # Already in graph format

    input_size = raw.get("input_size", 0)
    output_size = raw.get("output_size", 0)
    hidden_units_data = raw.get("hidden_units", [])
    num_hidden = len(hidden_units_data) if isinstance(hidden_units_data, list) else 0

    nodes = []
    connections = []

    # Input nodes
    for i in range(input_size):
        nodes.append({"id": f"input_{i}", "type": "input", "layer": 0})

    # Hidden nodes with cascade connections
    for h, unit in enumerate(hidden_units_data if isinstance(hidden_units_data, list) else []):
        nodes.append({"id": f"hidden_{h}", "type": "hidden", "layer": h + 1})
        weights = unit.get("weights", [])
        w_idx = 0
        # Connections from inputs
        for i in range(input_size):
            if w_idx < len(weights):
                connections.append({"from": f"input_{i}", "to": f"hidden_{h}", "weight": float(weights[w_idx])})
                w_idx += 1
        # Cascade connections from prior hidden units
        for prior_h in range(h):
            if w_idx < len(weights):
                connections.append({"from": f"hidden_{prior_h}", "to": f"hidden_{h}", "weight": float(weights[w_idx])})
                w_idx += 1

    # Output nodes and connections
    output_weights = raw.get("output_weights", [])
    for o in range(output_size):
        nodes.append({"id": f"output_{o}", "type": "output", "layer": num_hidden + 1})
        if o < len(output_weights):
            row = output_weights[o] if isinstance(output_weights[o], list) else output_weights
            w_idx = 0
            for i in range(input_size):
                if w_idx < len(row):
                    connections.append({"from": f"input_{i}", "to": f"output_{o}", "weight": float(row[w_idx])})
                    w_idx += 1
            for h in range(num_hidden):
                if w_idx < len(row):
                    connections.append({"from": f"hidden_{h}", "to": f"output_{o}", "weight": float(row[w_idx])})
                    w_idx += 1

    return {
        "input_units": input_size,
        "output_units": output_size,
        "hidden_units": num_hidden,
        "nodes": nodes,
        "connections": connections,
    }
```

Apply in `extract_network_topology()` after envelope unwrapping.

**Risks**: MEDIUM — Weight ordering assumption must match CasCor's actual serialization. Verify against a known topology response before deployment.

---

### P5-RC-03 — Uppercase Status Normalization Gap [HIGH, latent]

- **Severity**: HIGH (latent)
- **Status**: Latent compatibility bug — retained per directive
- **Proposal A**: Partially correct — retracted after title-case validation, but evidence preserved
- **Proposal B**: Correctly retained as HIGH latent

#### Description

CasCor's `TrainingStatus` enum (`state_machine.py:21-28`) uses uppercase `.name` values: `"STARTED"`, `"PAUSED"`, `"COMPLETED"`, `"STOPPED"`, `"FAILED"`. The `_normalize_status()` mapping (`state_sync.py:134-154`) contains lowercase and title-case entries but **no uppercase keys**. The relay callback (`cascor_service_adapter.py:222`) passes raw status to `_normalize_status()` with **no `.lower()` call**.

#### Path-Specific Behavior (verified)

| Path | `.lower()` Applied? | Status |
|---|---|---|
| Initial sync (`state_sync.py:70`) | **Yes** | Protected |
| Relay callback (`cascor_service_adapter.py:222`) | **No** | **Vulnerable** |

#### Reconciled Evidence from Both Proposals

**Proposal A correctly proved**: Current CasCor WebSocket broadcasts use **hardcoded title-case** strings (`"Started"`, `"Output"`) via `manager.py:111`, not enum `.name` values. These title-case strings ARE in the mapping. Therefore, the uppercase gap is **not currently triggered by CasCor in production**.

**Proposal B correctly proved**: The gap is still real because:

- `FakeCascorClient` (`fake_client.py:462-467`) sends uppercase status values, triggering the bug in tests
- Any future backend broadcasting `get_state_summary()` (which uses enum `.name`) would trigger it
- The asymmetric protection (sync has `.lower()`, relay does not) represents fragile coupling
- **Additional backend objects, other than the current CasCor backend, will be attached to the canopy application in the near future, and these new backends might pass uppercase values** (per directive)

#### Impact

- **Current CasCor**: No active impact (title-case is handled)
- **FakeCascorClient in tests**: Active — uppercase values fall through to default
- **Future backends**: Active — any backend sending uppercase enum names will fail to normalize
- **Architectural**: Fragile — one path protected, one path not

#### Recommended Fix

Primary recommendation — make `_normalize_status()` itself case-insensitive:

```python
@staticmethod
def _normalize_status(raw: str) -> str:
    """Normalize status string to canonical title-case representation.

    Case-insensitive: handles lowercase, title-case, and uppercase inputs.
    """
    key = raw.strip().lower() if isinstance(raw, str) else ""
    mapping = {
        "idle": "Stopped",
        "training": "Started",
        "started": "Started",
        "paused": "Paused",
        "complete": "Completed",
        "completed": "Completed",
        "failed": "Failed",
        "stopped": "Stopped",
        "running": "Started",
    }
    return mapping.get(key, "Stopped")
```

This is slightly stronger than the one-line relay-only fix (adding `.lower()` at the call site) and closes the compatibility gap at the normalization boundary itself, protecting all current and future callers.

---

### P5-RC-04 — WebSocket Relay State Callback Omits Fields [MODERATE]

- **Severity**: MODERATE
- **Status**: Active freshness/consistency issue
- **Correctly identified by**: Proposal A, Proposal B

#### Description

The relay callback (`cascor_service_adapter.py:218-225`) only forwards `status` and `phase` to `training_state.update_state()`, discarding `current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, `max_epochs`, `network_name`, and `timestamp`.

**Note**: The relay also handles `msg_type == "event"` at lines 228-235 for training-complete events. The data loss is specifically in the `state` message type handler.

#### Upstream Root Cause (unique finding from P4-B)

P4-B identified an important nuance: CasCor's WebSocket state broadcast itself sends only a minimal dict:

```python
create_state_message({"status": "Started", "phase": "Output"})
```

This means the relay callback is not actually discarding fields from the wire — CasCor doesn't send the additional fields via WebSocket. The upstream root cause is CasCor's minimal broadcast, not the relay's field filtering.

#### Impact

- `/api/state` endpoint returns stale `current_epoch` after initial sync
- **Status bar NOT affected** — reads from `/api/status` which makes fresh REST calls each poll cycle (confirmed by all proposals)

#### Recommended Fix

**Two-part** (combining relay-side and cascor-side):

1. **Immediate**: Expand relay callback to forward any additional fields present (safe — `TrainingState.update_state()` ignores `None` values):

```python
self._state_update_callback(
    status=status,
    phase=data.get("phase", ""),
    current_epoch=data.get("current_epoch"),
    current_step=data.get("current_step"),
    learning_rate=data.get("learning_rate"),
    max_hidden_units=data.get("max_hidden_units"),
    max_epochs=data.get("max_epochs"),
)
```

2. **Future**: Consider broadcasting full state from CasCor's `_register_ws_callbacks()`

---

### P5-RC-05 — Dashboard Ignores WebSocket Relay [LOW]

- **Severity**: LOW
- **Status**: Architectural choice, not current blocker
- **Correctly identified by**: Proposal A, Proposal B

#### Description

The dashboard uses `dcc.Interval` callbacks exclusively for data fetching (1000ms fast, 5000ms slow). A `websocket-data` div exists (`dashboard_manager.py:876`) but no Dash callback reads from it.

#### Impact

Latency/efficiency only. Not a functional blocker. HTTP polling at 1s intervals is adequate for training progress display.

#### Prerequisite Note

P5-RC-14 (relay broadcasts raw metrics) must be fixed before WebSocket consumption would work correctly.

---

### P5-RC-06 — CasCor TrainingMonitor.current_phase Never Updated [MODERATE]

- **Severity**: MODERATE — Cross-repo issue
- **Status**: Active correctness issue
- **Correctly identified by**: Proposal A, Proposal B
- **Repository**: juniper-cascor
- **Severity disagreement**: P4-B rated HIGH; P4-C rated LOW; resolved to MODERATE (see Section 7.3)

#### Description

CasCor's `TrainingMonitor` in `monitor.py:111` initializes `current_phase = "output"` and **never updates it** (verified: only one assignment to `current_phase` exists in the entire juniper-cascor codebase). When training enters candidate phase, `TrainingLifecycleManager` updates `training_state` and `state_machine` but NOT `monitor.current_phase`. Since `on_epoch_end()` reads `self.current_phase` at line 171, all metrics history entries have `phase: "output"` regardless of actual training phase.

**Validation detail**: Canopy's own `training_monitor.py:458` DOES update phase in `on_epoch_start()`, but this is a separate class used in demo mode — it does not affect the CasCor-side recording.

#### Impact

- Phase-colored scatter plots show all data as "Output" — no "Candidate" data distinguished
- Phase transition markers never appear on accuracy charts
- Not a display blocker (data still shows), but provides misleading phase information

#### Recommended Fix

In `juniper-cascor/src/api/lifecycle/manager.py`, update `monitor.current_phase` during phase transitions:

```python
# When entering candidate phase:
self.monitor.current_phase = "candidate"
# When returning to output phase:
self.monitor.current_phase = "output"
```

Can be shipped independently — Canopy fixes work without this but will show incorrect phase labels.

---

### P5-RC-07 — State Sync Metrics History Stored Without Normalization [MODERATE]

- **Severity**: MODERATE (latent, low current impact)
- **Status**: Latent
- **Correctly identified by**: Proposal A, Proposal B

#### Description

During initial state sync, `CascorStateSync.sync()` (`state_sync.py:115-129`) stores raw CasCor metrics directly into `state.metrics_history` without passing entries through `_normalize_metric()` or `_to_dashboard_metric()`. Raw entries use CasCor field names (`loss`, `accuracy`, `validation_loss`) — different from both the canonical flat format and the dashboard's nested format.

#### Reconciled Impact

- **Proposal A** correctly reduced practical severity: `SyncedState.metrics_history` has **no active downstream consumer** — `main.py` lines 190-200 only extract `status`, `phase`, `current_epoch`, etc. from the synced state
- **Proposal B** correctly preserved the structural concern: if future code pre-populates charts from synced metrics on connect (e.g., to avoid cold-start blank display), the data would be in the wrong format

As both proposals note, this is a "double latent issue" — even normalizing to flat keys would still not match the dashboard without the `_to_dashboard_metric()` transformation.

#### Recommended Fix

Apply both normalization steps to synced metrics:

```python
state.metrics_history = [
    CascorServiceAdapter._to_dashboard_metric(
        CascorServiceAdapter._normalize_metric(m)
    )
    for m in raw_history
]
```

---

### P5-RC-08 — State Sync Bypasses Adapter Normalization Entirely [MODERATE]

- **Severity**: MODERATE
- **Status**: Structural issue
- **Correctly identified by**: Proposal B
- **Proposal A**: Not separated as its own issue

#### Description

`ServiceBackend.initialize()` (`service_backend.py:189`) passes the **raw client** to `CascorStateSync`:

```python
self._synced_state = CascorStateSync(self._adapter._client).sync()
```

This bypasses the adapter's entire normalization layer, creating three normalization gaps:

1. **Metrics** (P5-RC-07): Stored in raw CasCor format
2. **Training params** (P5-RC-10): Stored with raw CasCor parameter names
3. **Status** (P5-RC-03): Partially normalized but affected by the uppercase gap on the relay path

This is the structural root cause underlying P5-RC-07, P5-RC-10, and partially P5-RC-03.

#### Recommended Fix

Change state sync to depend on the adapter (or adapter-exposed transformation helpers), not the raw client. This keeps format logic in one place and reduces future drift.

---

### P5-RC-09 — `/api/metrics` Current Snapshot Also Flat [MODERATE]

- **Severity**: MODERATE
- **Status**: Active second code path (same root cause as P5-RC-01)
- **Proposal A**: Subsumed into RC-01
- **Proposal B**: Correctly separated

#### Description

The `/api/metrics` endpoint (current metrics snapshot) follows the same broken path as `/api/metrics/history`. `get_current_metrics()` at `cascor_service_adapter.py:86-94` also uses `_normalize_metric()` producing flat keys.

#### Classification

This is **not a separate root cause**, but it **must remain a separately tracked implementation target** so the `_to_dashboard_metric()` fix is applied to both code paths.

#### Recommended Fix

Apply `_to_dashboard_metric()` to the current metrics snapshot path alongside the history path.

---

### P5-RC-10 — State Sync Params Not Mapped Through Param Map [MODERATE]

- **Severity**: MODERATE (structural, low current impact)
- **Status**: Structural issue
- **Correctly identified by**: Proposal B
- **Proposal A**: Not separated

#### Description

During initial state sync (`state_sync.py:98-103`), training parameters are stored using raw CasCor names (`learning_rate`, `max_hidden_units`, `epochs_max`) rather than being mapped through `_CANOPY_TO_CASCOR_PARAM_MAP` to Canopy's `nn_*/cn_*` namespace.

#### Impact

When `main.py:189-202` reads `synced.params` and applies them to the parameter panel, the dashboard receives CasCor parameter names instead of Canopy parameter names, potentially causing parameter labels to not match values.

#### Recommended Fix

During sync, map params through the reverse mapping so synced state uses Canopy names consistently.

---

### P5-RC-11 — Hardcoded `localhost:8050` URLs in MetricsPanel [MODERATE]

- **Severity**: MODERATE
- **Status**: Active deployment bug
- **Correctly identified by**: Proposal A, Proposal B
- **Count verified**: 6 instances (P4-C initially reported 2, corrected to 6 in validation)

#### Description

`MetricsPanel` contains 6 hardcoded `http://localhost:8050` URLs (all verified):

| Line | URL Path | Purpose |
|---|---|---|
| 1000 | `/api/network/stats` | Network statistics |
| 1021 | `/api/state` | Training state |
| 1155 | `/api/v1/metrics/layouts` | Layout list (GET) |
| 1187 | `/api/v1/metrics/layouts` | Layout save (POST) |
| 1231 | `/api/v1/metrics/layouts/{name}` | Layout load (GET) |
| 1274 | `/api/v1/metrics/layouts/{name}` | Layout delete (DELETE) |

#### Impact

Breaks when Canopy runs in Docker, behind reverse proxy, or on non-standard host/port — all of which are active use cases for the Juniper ecosystem (juniper-deploy uses Docker Compose).

#### Recommended Fix

Replace hardcoded absolute URLs with **relative API paths** where possible (e.g., `/api/network/stats` instead of `http://localhost:8050/api/network/stats`). Relative paths are simpler and lower risk than introducing a custom URL builder.

---

### P5-RC-12 — Dead Parameter Mapping (`cn_training_iterations` → `candidate_epochs`) [LOW]

- **Severity**: LOW
- **Status**: Active parameter bug
- **Correctly identified by**: Proposal A, Proposal B
- **Reclassified**: Not "dead code" (Proposal A's Phase 4 term) — the mapping executes but the update is silently dropped

#### Description

The mapping at `cascor_service_adapter.py:364` targets `candidate_epochs`, but CasCor's `TrainingParamUpdateRequest` (`api/models/training.py:45-54`) does not accept it and `candidate_epochs` is NOT in the `updatable_keys` set (`manager.py:545-553`). While `candidate_epochs` exists as a CasCor network configuration attribute, it is NOT exposed as a runtime-updatable parameter through the REST API.

#### Recommended Fix

Remove or disable this mapping for runtime PATCH flows unless/until CasCor exposes `candidate_epochs` as a valid updatable parameter.

---

### P5-RC-12b — `patience` / `nn_growth_convergence_threshold` Semantic Mismatch [LOW]

- **Severity**: LOW
- **Status**: Active semantic mismatch
- **Proposal A**: Partial (noted as part of RC-09)
- **Proposal B**: Correctly separated

#### Description

`patience` is an integer epoch count (epochs to wait before stopping) but `nn_growth_convergence_threshold` semantically implies a float threshold value. The parameter panel displays an integer patience value under a "Growth Convergence Threshold" label — functionally correct but misleading.

#### Recommended Fix

Prefer label/help-text clarification over broad key renames to avoid creating large downstream churn.

---

### P5-RC-13 — `candidate_learning_rate` Not Mapped [LOW]

- **Severity**: LOW
- **Status**: Active
- **Correctly identified by**: Proposal A, Proposal B

#### Description

CasCor's `PATCH /v1/training/params` accepts `candidate_learning_rate` as updatable (`routes/training.py:49`, `manager.py:545-553`), but `_CANOPY_TO_CASCOR_PARAM_MAP` has no entry for it.

#### Impact

Users cannot adjust candidate learning rate from the Canopy dashboard.

#### Recommended Fix

Add `candidate_learning_rate` mapping to `_CANOPY_TO_CASCOR_PARAM_MAP` and expose through the parameter flow.

---

### P5-RC-14 — WebSocket Relay Broadcasts Unnormalized Metrics [LOW, latent]

- **Severity**: LOW (latent)
- **Status**: Latent
- **Correctly identified by**: Proposal A, Proposal B

#### Description

The relay loop (`cascor_service_adapter.py:203-206`) broadcasts raw CasCor metrics payloads to browser clients with zero normalization. CasCor field names (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`) are forwarded verbatim.

#### Impact

Currently latent because dashboard doesn't consume WebSocket data (P5-RC-05). Becomes an active bug if P5-RC-05 is addressed.

#### Recommended Fix

Defer until/if dashboard WebSocket consumption is implemented. Then apply the same normalization pipeline used by REST paths.

---

### P5-RC-15 — Double Initialization on Fallback-to-Demo Path [LOW]

- **Severity**: LOW
- **Status**: Active
- **Correctly identified by**: Proposal A, Proposal B

#### Description

In `main.py`, when CasCor is unreachable:

- Line 177: `await backend.initialize()` — inside the fallback block (after creating demo backend at 176)
- Line 180: `await backend.initialize()` — unconditionally after the if block

The demo backend's `initialize()` calls `self._demo.start()` which starts the training simulation thread. Double calling could start duplicate threads depending on idempotency guarantees.

#### Recommended Fix

Guard the second initialization with `else` clause or `initialized` flag to prevent double `backend.initialize()`.

---

### P5-RC-16 — Phase 1 Test Coverage Gap [LOW]

- **Severity**: LOW
- **Status**: Preventive
- **Correctly identified by**: Proposal A, Proposal B

#### Description

All Phase 1 test classes validate flat key production (`"train_loss" in result[0]`) but never verify that the output is compatible with the dashboard's nested access patterns. No contract tests compare demo and service output shapes. Zero test files reference `BackendProtocol`.

#### Recommended Fix

Add contract tests comparing demo and service output shapes. Update existing tests to verify nested format after P5-RC-01 fix is applied.

---

### P5-RC-17 — Dual Status Normalization Inconsistency [INFO]

- **Severity**: INFO — Architectural observation
- **Status**: Observation
- **Correctly identified by**: Proposal A, Proposal B

#### Description

Two independent normalization paths produce different representations:

- **Path A** (`ServiceBackend.get_status()`): Uses `.upper()` comparison, returns boolean flags (`is_running`, `is_paused`) plus raw `fsm_status`
- **Path B** (relay → `_normalize_status()`): Returns title-case strings (`"Started"`, `"Paused"`)

Not a functional blocker. Both paths produce values the dashboard can consume correctly through their respective consumers. The P5-RC-03 fix (making `_normalize_status()` case-insensitive) partially addresses this.

---

### P5-RC-18 — No Canonical Backend Contract [SYSTEMIC]

- **Severity**: SYSTEMIC — Underlying architectural root cause
- **Status**: Structural
- **Correctly identified by**: Proposal A, Proposal B

#### Description

`BackendProtocol` (`protocol.py:59-140`) returns `Dict[str, Any]` for all methods. No TypedDict, dataclass, or structured return types are used. `data_adapter.py` defines `TrainingMetrics`, `NetworkNode`, `NetworkConnection`, and `NetworkTopology` dataclasses, but `BackendProtocol` does not reference them, and neither backend implementation returns instances of these types. They are dead abstractions.

This is the deepest root cause underlying P5-RC-01, P5-RC-02, P5-RC-07, P5-RC-09, and P5-RC-14. Without enforced contracts, demo and service modes silently diverge in output format.

| Data Path | Demo Mode | Service Mode | Match |
|---|---|---|---|
| Metrics history | Nested (`metrics.loss`) | Flat (`train_loss`) | **No** |
| Current metrics | Nested | Flat | **No** |
| Status | Flat (`is_running`) | Flat (`is_running`) | Yes |
| Topology | Graph-oriented | Weight-oriented (passthrough) | **No** |
| State sync metrics | N/A | Raw CasCor | **No** |
| Relay broadcast | N/A | Raw CasCor | **No** |
| Dataset | Includes data arrays | Metadata only | Partial |

#### Recommended Fix

Not required to restore the dashboard immediately, but should be addressed with:

- TypedDict/dataclass definitions for backend return types
- Demo vs service contract tests (part of FIX-K/FIX-H)
- Possibly shared adapter output models

---

### KL-1 — Dataset Scatter Plot Empty in Service Mode [Known Limitation]

- **Status**: Known architectural limitation
- **Correctly identified by**: Proposal B (as known limitation); Proposal A (as active issue — overcategorized)

#### Description

CasCor's `/v1/dataset` endpoint (`manager.py:499-509`) returns metadata only (`loaded`, `train_samples`, `test_samples`, `input_features`, `output_features`). `ServiceBackend.get_dataset()` maps this to `num_samples`, `num_features`, `num_classes` — no `inputs` or `targets` arrays. `dataset_plotter._create_scatter_plot()` expects `inputs` and `targets` arrays and shows "No data available" when they are absent.

#### Impact

Dataset scatter plot always shows "No data available" in service mode.

#### Resolution

Not a bug — it is an architectural limitation of CasCor's API. Requires either:

- CasCor API extension to return data arrays, or
- Direct juniper-data integration to fetch data separately

---

## 6. Cross-Proposal Agreement Matrices

### 6.1 Phase 5 Proposal Agreement Matrix

| Final Issue | Proposal A (7f73219c) | Proposal B (8b7d1ee8) | Resolution |
|---|:---:|:---:|---|
| P5-RC-01 | ✓ | ✓ | Unanimous |
| P5-RC-02 | ✓ | ✓ | Unanimous |
| P5-RC-03 | Retracted (title-case evidence) | ✓ (HIGH latent) | Retained per directive; A's evidence preserved |
| P5-RC-04 | ✓ | ✓ | Unanimous |
| P5-RC-05 | ✓ | ✓ | Unanimous |
| P5-RC-06 | ✓ | ✓ | Unanimous |
| P5-RC-07 | ✓ | ✓ | Unanimous |
| P5-RC-08 | — | ✓ | Retained (B's structural finding) |
| P5-RC-09 | S (subsumed by RC-01) | ✓ | Retained as separate implementation target |
| P5-RC-10 | — | ✓ | Retained (B's unique finding) |
| P5-RC-11 | ✓ | ✓ | Unanimous |
| P5-RC-12 | ✓ | ✓ | Unanimous |
| P5-RC-12b | P | ✓ | Retained (B's separation) |
| P5-RC-13 | ✓ | ✓ | Unanimous |
| P5-RC-14 | ✓ | ✓ | Unanimous |
| P5-RC-15 | ✓ | ✓ | Unanimous |
| P5-RC-16 | ✓ | ✓ | Unanimous |
| P5-RC-17 | ✓ | ✓ | Unanimous |
| P5-RC-18 | ✓ | ✓ | Unanimous |
| KL-1 | P (as active issue) | ✓ (as known limitation) | Classified as limitation |

### 6.2 Phase 4 Proposal Agreement Matrix

| Final Issue | P4-A (002192f3) | P4-B (66a019dc) | P4-C (cd8254d3) | P4-D (d7dcbd5a) | Agreement |
|---|:---:|:---:|:---:|:---:|---|
| P5-RC-01 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-02 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-03 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-04 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-05 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-06 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-07 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-08 | — | ✓ | — | ✓ | 2/4 |
| P5-RC-09 | — | ✓ | S | ✓ | 2/4 + 1 subsumed |
| P5-RC-10 | — | — | — | ✓ | 1/4 |
| P5-RC-11 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-12 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-12b | P | ✓ | P (part of RC-9) | ✓ | 4/4 underlying |
| P5-RC-13 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-14 | — | ✓ | ✓ | ✓ | 3/4 |
| P5-RC-15 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| P5-RC-16 | ✓ | — | ✓ | ✓ | 3/4 |
| P5-RC-17 | — | — | ✓ | ✓ | 2/4 |
| P5-RC-18 | ✓ | ✓ | ✓ | ✓ | 4/4 |
| KL-1 | ✓ | ✓ | ✓ | ✓ | 4/4 |

### 6.3 Phase 3 Proposal Agreement Matrix

| Final Issue | v1 | v2 | v3 | v4 | v5 | v6 | v7 | Consensus |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| P5-RC-01 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 |
| P5-RC-02 | — | ✓ | — | ✓ | — | — | — | 2/7 |
| P5-RC-03 | — | — | — | ✓ | — | — | ✓ | 2/7 |
| P5-RC-04 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 |
| P5-RC-05 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 |
| P5-RC-06 | — | — | — | — | ✓ | — | — | 1/7 |
| P5-RC-07 | ✓ | — | ✓ | — | ✓ | ✓ | ✓ | 5/7 |
| P5-RC-08 | — | — | — | — | — | — | ✓ | 1/7 |
| P5-RC-09 | — | — | — | — | — | ✓ | — | 1/7 |
| P5-RC-10 | — | — | — | — | — | — | ✓ | 1/7 |
| P5-RC-11 | — | — | — | ✓ | — | — | — | 1/7 |
| P5-RC-12 | — | ✓ | — | ✓ | — | — | — | 2/7 |
| P5-RC-12b | — | ✓ | — | — | — | — | — | 1/7 |
| P5-RC-13 | — | — | — | ✓ | — | — | — | 1/7 |
| P5-RC-14 | — | — | — | ✓ | — | — | ✓ | 2/7 |
| P5-RC-15 | — | — | — | — | ✓ | ✓ | — | 2/7 |
| P5-RC-16 | — | — | — | — | ✓ | — | ✓ | 2/7 |
| P5-RC-17 | — | — | — | ✓ | — | — | — | 1/7 |
| P5-RC-18 | — | — | — | ✓ | — | ✓ | ✓ | 3/7 |
| KL-1 | — | — | — | ✓ | — | — | — | 1/7 |

**Analysis**: 7/7 consensus on P5-RC-01, P5-RC-04, P5-RC-05 (the original Phase 2 findings). 12 issues found by only 1-2 of the 7 proposals, underscoring the value of the multi-proposal approach. Most comprehensive Phase 3 proposals: v4 (widest scope), v5 (unique cross-repo discovery), v6/v7 (systemic architectural analysis).

---

## 7. Disagreements and Final Resolutions

### 7.1 Uppercase Status Gap: Removed vs Retained

| Position | Source |
|---|---|
| Removed after title-case validation | Proposal A |
| Retained as HIGH latent | Proposal B |

**Final resolution**: Retain as `P5-RC-03 HIGH (latent)`.

**Rationale**: Proposal A's evidence is valid and preserved (current CasCor sends title-case). Proposal B's classification better matches future-backend and test risk. The directive explicitly requires retention for future backend compatibility. The fix is trivial and low-risk.

### 7.2 Topology Severity: CRITICAL vs MODERATE

| Proposal | Rating |
|---|---|
| P4-A, P4-B, P4-D, Proposal A, Proposal B | CRITICAL |
| P4-C | MODERATE |

**Final resolution**: **CRITICAL**. The network topology visualization is completely non-functional in service mode — the validation guard (`network_visualizer.py:351`) always triggers because `input_units` is never present in CasCor's response. This makes it a display blocker equivalent to the metrics mismatch. P4-C's MODERATE rating does not account for the fact that the visualization is entirely blank, not merely degraded.

### 7.3 CasCor Phase Bug Severity

| Proposal | Rating |
|---|---|
| P4-A, P4-D | MODERATE |
| P4-B | HIGH |
| P4-C | LOW |

**Final resolution**: **MODERATE**. This is a real cross-repo bug confirmed by validation (only one assignment to `current_phase` exists). It affects phase labels in metrics but does not prevent data from displaying. P4-B's HIGH rating overestimates impact (phase labels are cosmetic, not functional). P4-C's LOW rating underestimates impact (phase-based visualizations are non-functional, not merely imprecise).

### 7.4 Hardcoded URL Count: 2 vs 6

| Proposal | Count |
|---|---|
| P4-C (initial) | 2 |
| P4-A, P4-B, P4-C (corrected), P4-D, both Phase 5 | 6 |

**Final resolution**: **6 confirmed** at lines 1000, 1021, 1155, 1187, 1231, 1274.

### 7.5 Hardcoded URLs Severity: MODERATE vs LOW

| Proposal | Rating |
|---|---|
| P4-A, P4-B, P4-D | MODERATE |
| P4-C | LOW |

**Final resolution**: **MODERATE**. This issue affects deployment portability in Docker, reverse proxy, and non-standard port scenarios — all of which are active use cases for the Juniper ecosystem (juniper-deploy uses Docker Compose).

### 7.6 `/api/metrics` Snapshot: Separate Issue vs Subsumed

| Proposal | Treatment |
|---|---|
| Proposal A, P4-C | Subsumed by P5-RC-01 |
| Proposal B, P4-B, P4-D | Separate issue |

**Final resolution**: Listed separately as `P5-RC-09` to ensure both code paths are addressed during implementation, but recognized as same root cause as P5-RC-01.

### 7.7 Dataset Scatter: Active Bug vs Known Limitation

| Proposal | Classification |
|---|---|
| Proposal A, P4-A, P4-B, P4-D | Active issue (MODERATE) |
| Proposal B, P4-C | Known limitation |

**Final resolution**: **Known limitation**. This is not a bug — it is an architectural limitation of CasCor's API. Requires CasCor API extension or direct juniper-data integration to resolve.

### 7.8 `candidate_epochs` Mapping Classification

| Proposal | Classification |
|---|---|
| P4-A, P4-B, P4-D | "Dead code" |
| Proposal A | Reclassified to "non-functional mapping" |

**Final resolution**: **Non-functional runtime mapping**. Not dead code — the mapping executes successfully — but `candidate_epochs` is not in CasCor's `updatable_keys`, so the update is silently dropped.

### 7.9 Relay Raw Metrics Severity: MODERATE vs LOW

| Proposal | Rating |
|---|---|
| P4-B | MODERATE |
| P4-C, P4-D | LOW |

**Final resolution**: **LOW (latent)**. The bug is currently inactive because the dashboard doesn't consume WebSocket data (P5-RC-05). The issue becomes relevant only if P5-RC-05 is addressed.

### 7.10 State Sync Metrics Severity

**Final resolution**: MODERATE structural issue with low current impact. Proposal A correctly lowered current practical impact (no downstream consumer). Proposal B correctly preserved the structural concern.

---

## 8. Architectural Root Cause Analysis and Dependency Graph

### 8.1 The Fundamental Problem (Consensus Across All Proposals)

The Juniper Canopy system has **multiple distinct ingress paths** for data into the dashboard, each independently determining its output format. No shared function, TypedDict, or contract enforces structural compatibility between these paths:

| Ingress Path | Current Format | Dashboard Expects | Works? |
|---|---|---|---|
| Demo mode metrics | Nested (`metrics.loss`) | Nested | **Yes** |
| REST metrics history (polling) | Flat (`train_loss`) | Nested | **No** |
| REST current metrics (polling) | Flat (`train_loss`) | Nested | **No** |
| State sync on connect | Raw CasCor (`loss`) | Nested | **No** |
| WebSocket relay (broadcast) | Raw CasCor (`loss`) | Nested | **No** (unused) |
| Demo mode topology | Graph-oriented | Graph-oriented | **Yes** |
| REST topology (polling) | Weight-oriented (passthrough) | Graph-oriented | **No** |
| Status bar | Flat (`is_running`) | Flat | **Yes** |

### 8.2 Why the Status Bar Works (All Proposals Agree)

The status bar path is the exception that proves the rule. `ServiceBackend.get_status()` was specifically designed to produce flat keys that match what the status bar reads. Both demo and service backends happen to produce matching output for status data. This success created false confidence that the normalization approach was complete.

### 8.3 How the Problem Compounds (Best Articulated by P4-D)

1. **Phase 1** defined normalization targeting flat keys (correct for CasCor → Canopy boundary)
2. **Dashboard** was built against demo mode's nested keys (correct for demo mode)
3. **No mechanism** detects the mismatch between (1) and (2)
4. **Tests** validate flat key production without testing dashboard compatibility
5. **Status bar success** masks the metrics failure
6. **Topology** follows the same pattern: demo produces graph-oriented, service passes through weight-oriented
7. **State sync** bypasses even the adapter normalization, creating a third format variant

### 8.4 Root Cause Dependency Graph

```text
P5-RC-18  SYSTEMIC: No canonical backend contract
├── P5-RC-01  CRITICAL: Metrics flat vs nested mismatch ──── PRIMARY BLOCKER
│   ├── P5-RC-09  MODERATE: /api/metrics current snapshot also flat
│   ├── P5-RC-07  MODERATE: State sync metrics history unnormalized
│   └── P5-RC-14  LOW: WebSocket relay broadcasts raw metrics
│
├── P5-RC-02  CRITICAL: Topology weight vs graph mismatch ──── SECONDARY BLOCKER
│
├── P5-RC-03  HIGH (latent): Status case fragility in relay path
│   └── P5-RC-17  INFO: Dual status normalization inconsistency
│
├── P5-RC-08  MODERATE: State sync bypasses adapter normalization
│   ├── P5-RC-07  (structural parent)
│   └── P5-RC-10  MODERATE: State sync params not mapped
│
├── P5-RC-04  MODERATE: Relay state callback narrow / upstream WS minimal
│
├── P5-RC-05  LOW: Dashboard ignores WebSocket relay
│
├── P5-RC-06  MODERATE: CasCor phase bug (cross-repo)
│
├── P5-RC-11  MODERATE: Hardcoded deployment URLs
│
├── P5-RC-12  LOW: Dead parameter mapping (candidate_epochs)
│   ├── P5-RC-12b  LOW: patience semantic mismatch
│   └── P5-RC-13  LOW: candidate_learning_rate unmapped
│
├── P5-RC-15  LOW: Double initialization on fallback
│
└── P5-RC-16  LOW: Phase 1 test coverage gap

KL-1: Known Limitation — Dataset scatter plot empty (architectural)
```

---

## 9. False Positives and Retractions

Three false positives were identified and retracted across Phase 3 and Phase 4 analyses. All four Phase 4 proposals documented these consistently:

### FP-1: `/api/state` Parameter Initialization Uses Hardcoded Defaults

- **Originally claimed by**: Phase 3 proposals v1 (RC-4), v3 (RC-4)
- **Retracted by**: v1, v3 (self-corrected during validation)
- **Confirmed false by**: All 4 Phase 4 proposals
- **Reason**: Code at `main.py:612-614` calls `get_canopy_params()` and overlays real CasCor values. Parameters are correctly populated from the external CasCor instance.

### FP-2: Fallback-to-Demo Path Doesn't Re-Sync `training_state`

- **Originally claimed by**: Phase 3 proposal v5 (RC-6)
- **Retracted by**: v5 (self-corrected during validation)
- **Confirmed false by**: All 4 Phase 4 proposals
- **Reason**: After fallback replaces `backend` with demo backend, execution continues to the demo-mode sync block which correctly syncs `training_state`. The double initialization (P5-RC-15) was preserved as a separate, confirmed issue.

### FP-3: `/api/metrics` Current Snapshot as Independent Root Cause

- **Originally claimed by**: Phase 3 proposal v6
- **Reclassified by**: P4-C (subsumed into RC-1)
- **Status**: Not false in symptom, but reclassified — same root cause as P5-RC-01
- **Treatment**: Listed separately as P5-RC-09 for implementation tracking

### Explicit Non-Retraction Note

**P5-RC-03 (uppercase status normalization gap) is NOT retracted in this final document.** Proposal A's title-case evidence is preserved as contextual information, but the issue remains active as a latent bug per directive — future backends may send uppercase values.

---

## 10. Verified Working Paths

The following subsystems function correctly in service mode (confirmed by all proposals):

| Subsystem | Mechanism | Verified |
|---|---|---|
| Status bar (is_running, phase, epoch, hidden units) | `/api/status` → fresh REST calls → flat keys → status bar reads flat keys | ✓ All proposals |
| Decision boundary visualization | `get_decision_boundary()` transforms `grid_x`/`grid_y` → `xx`/`yy`/`Z` | ✓ P4-B, P4-D |
| Dataset metadata display | `get_dataset()` maps `train_samples` → `num_samples` | ✓ P4-B, P4-D |
| Training controls (start/stop/pause/resume/reset) | REST forwarding with proper error handling | ✓ All proposals |
| Parameter updates (apply_params write path) | `_CANOPY_TO_CASCOR_PARAM_MAP` correctly maps canopy → cascor names | ✓ All proposals |
| WebSocket relay connection/broadcast | Messages correctly relayed to browser clients | ✓ All proposals |
| ResponseEnvelope unwrapping | All 14 Phase 1 fixes correctly implemented | ✓ All proposals |
| Non-destructive attach to running CasCor | Attach endpoint handles non-destructive mode | ✓ P4-A, P4-B |

---

## 11. Consolidated Fix Recommendations

### FIX-A: Metrics Format Transformation [P5-RC-01, P5-RC-09]

- **Priority**: P0 — CRITICAL
- **Effort**: Small (1-2 hours)
- **Consensus**: Unanimous across all proposals

Add `_to_dashboard_metric()` as described in P5-RC-01 detail. Apply in both:

- `_ServiceTrainingMonitor.get_recent_metrics()` — wrapping each entry after `_normalize_metric()`
- `_ServiceTrainingMonitor.get_current_metrics()` — wrapping result after `_normalize_metric()`

**Advantages**: Single transformation point; dashboard code untouched; demo path untouched; each layer independently testable; minimal blast radius.

**Risks**: LOW — `network_topology` sub-dict will only contain `hidden_units`, but dashboard only reads that field.

### FIX-B: Network Topology Transformation [P5-RC-02]

- **Priority**: P0 — CRITICAL
- **Effort**: Medium (2-3 hours)
- **Consensus**: All proposals agree; transformation code synthesized from both

Add `_transform_topology()` as described in P5-RC-02 detail. Apply in `extract_network_topology()` after envelope unwrapping, with format detection (`"input_units" in raw` → already graph format, skip transformation).

**Risks**: MEDIUM — Weight ordering assumption must match CasCor's actual serialization. Verify against a known topology response before deployment.

### FIX-C: Status Normalization Hardening [P5-RC-03]

- **Priority**: P1 — HIGH
- **Effort**: Small (<1 hour)
- **Consensus**: Both proposals agree the gap exists; approach improved from relay-only fix to centralized case-insensitive normalization

Make `_normalize_status()` internally case-insensitive as described in P5-RC-03 detail. This protects all current and future callers, including the relay callback, and handles future backends that may send uppercase values.

### FIX-D: WebSocket Relay State Field Forwarding [P5-RC-04]

- **Priority**: P2 — MODERATE
- **Effort**: Small (30 minutes)

Expand relay callback to forward optional fields (`current_epoch`, `current_step`, `learning_rate`, `max_hidden_units`, `max_epochs`) alongside `status` and `phase`. Safe because `TrainingState.update_state()` ignores `None` values.

### FIX-E: State Sync Normalization [P5-RC-07, P5-RC-08, P5-RC-10]

- **Priority**: P2 — MODERATE
- **Effort**: Small-Medium (1-2 hours)
- **Dependencies**: FIX-A (needs `_to_dashboard_metric()`)

Either route state sync through the adapter or apply normalization pipeline to synced state during `sync()`:

1. Normalize synced metrics history through both `_normalize_metric()` and `_to_dashboard_metric()`
2. Map synced params into Canopy namespace
3. Consider passing the adapter to state sync instead of the raw client

### FIX-F: Hardcoded Localhost URLs [P5-RC-11]

- **Priority**: P2 — MODERATE
- **Effort**: Trivial (15 minutes)

Replace all 6 hardcoded `http://localhost:8050` URLs in `metrics_panel.py` with relative paths (e.g., `/api/network/stats`).

### FIX-G: CasCor Phase Tracking [P5-RC-06]

- **Priority**: P3 — MODERATE (cross-repo)
- **Repository**: juniper-cascor
- **Effort**: Small (1 hour)

Update `TrainingMonitor.current_phase` in `TrainingLifecycleManager` during phase transitions. Independent of Canopy fixes.

### FIX-H: Parameter Mapping Corrections [P5-RC-12, P5-RC-12b, P5-RC-13]

- **Priority**: P4 — LOW
- **Effort**: Small (1 hour)

1. Remove or disable dead `cn_training_iterations` → `candidate_epochs` mapping
2. Clarify `patience` / `nn_growth_convergence_threshold` labeling (prefer help-text over key renames)
3. Add `cn_candidate_learning_rate` → `candidate_learning_rate` mapping

### FIX-I: WebSocket Relay Metric Normalization [P5-RC-14]

- **Priority**: P4 — LOW (future-proofing)
- **Effort**: Small (<1 hour)

Apply normalization to metrics messages before broadcasting. Only necessary if P5-RC-05 is addressed.

### FIX-J: Double Initialization Guard [P5-RC-15]

- **Priority**: P5 — LOW
- **Effort**: Trivial (15 minutes)

Guard fallback initialization with `else` clause or `initialized` flag.

### FIX-K: Contract Tests [P5-RC-16, P5-RC-18]

- **Priority**: P2 — MODERATE (preventive)
- **Effort**: Medium (2-3 hours)
- **Dependencies**: FIX-A, FIX-B

Add tests comparing demo and service output shapes. Update existing tests to verify nested format. Add uppercase status normalization tests.

---

## 12. Implementation Priority and Ordering

### Tier 0: Restore Core Functionality (CRITICAL)

| Order | Fix | Issues | Effort | Risk | Repo |
|---|---|---|---|---|---|
| 1 | FIX-A | P5-RC-01, P5-RC-09 | Small (1-2 hrs) | Low | juniper-canopy |
| 2 | FIX-B | P5-RC-02 | Medium (2-3 hrs) | Medium | juniper-canopy |

**After Tier 0**: Metrics charts display live data. Topology renders. Dashboard is functionally usable.

FIX-A and FIX-B can be implemented in parallel. FIX-A alone will restore metrics charts.

### Tier 1: Harden Integration Contract (HIGH + MODERATE)

| Order | Fix | Issues | Effort | Risk | Repo | Dependencies |
|---|---|---|---|---|---|---|
| 3 | FIX-C | P5-RC-03 | Small (<1 hr) | Low | juniper-canopy | None |
| 4 | FIX-D | P5-RC-04 | Small (30 min) | Low | juniper-canopy | None |
| 5 | FIX-E | P5-RC-07, P5-RC-08, P5-RC-10 | Small-Med (1-2 hrs) | Low | juniper-canopy | FIX-A |
| 6 | FIX-F | P5-RC-11 | Trivial (15 min) | None | juniper-canopy | None |
| 7 | FIX-K | P5-RC-16, P5-RC-18 | Medium (2-3 hrs) | None | juniper-canopy | FIX-A, FIX-B |

### Tier 2: Cross-Repo and UX Consistency

| Order | Fix | Issues | Effort | Risk | Repo | Dependencies |
|---|---|---|---|---|---|---|
| 8 | FIX-G | P5-RC-06 | Small (1 hr) | Low | juniper-cascor | None |
| 9 | FIX-H | P5-RC-12, P5-RC-12b, P5-RC-13 | Small (1 hr) | Low | juniper-canopy | None |

### Tier 3: Deferred / Optional

| Order | Fix | Issues | Effort | Risk | Repo | Dependencies |
|---|---|---|---|---|---|---|
| 10 | FIX-J | P5-RC-15 | Trivial (15 min) | None | juniper-canopy | None |
| 11 | FIX-I | P5-RC-14 | Small (<1 hr) | Low | juniper-canopy | P5-RC-05 resolution |
| — | Future | P5-RC-05 | Medium-Large | Medium | juniper-canopy | FIX-I |
| — | Future | KL-1 | Large-XL | Medium | cross-repo | CasCor API extension |

### Fix Dependency Graph

```text
FIX-A (P5-RC-01, RC-09) ──┐
                           ├── FIX-E (P5-RC-07, RC-08, RC-10) ── FIX-K (P5-RC-16, RC-18)
FIX-B (P5-RC-02) ─────────┘
                               ↑ parallel with ↓
FIX-C (P5-RC-03) ── FIX-D (P5-RC-04) ── FIX-F (P5-RC-11)
                               ↓
                     FIX-G (P5-RC-06, cross-repo)
                     FIX-H (P5-RC-12, RC-12b, RC-13)
                     FIX-I (P5-RC-14, deferred)
                     FIX-J (P5-RC-15)
```

---

## 13. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `_to_dashboard_metric()` misses a field used by frontend | Low | High | Compare against demo payload shape; contract tests (FIX-K) |
| `_to_dashboard_metric()` breaks demo mode | Low | High | Only applied in service path; demo path untouched |
| Topology weight ordering assumption incorrect for cascade architecture | Medium | Medium | Verify against actual CasCor response; add integration test |
| Status normalization fix changes existing title-case behavior | Low | Low | Case-insensitive normalization preserves current outputs |
| Falsy values (epoch=0, loss=0.0) treated as missing | Medium | Medium | Use `_first_defined()` helper (already exists); `is not None` checks |
| FakeCascorClient divergence masks new issues | High | Medium | Add contract tests comparing fake and real response shapes |
| Multiple simultaneous fixes introduce regressions | Medium | Medium | Fix and test one tier at a time; run full suite between |
| Demo mode regresses from shared code changes | Low | High | Demo path untouched by all fixes; add regression test |
| CasCor cross-repo fix (RC-06) requires coordination | Medium | Low | Canopy fixes are independent; phase labels degrade gracefully |
| Phase 1 test assertions need updating for nested format | High | Low | Expected; update assertions as part of FIX-A |
| State sync refactor introduces startup regressions | Medium | Medium | Keep changes minimal; reuse adapter helpers; test attach/startup |
| Relative URL cleanup breaks non-browser/test assumptions | Low | Medium | Use same-origin relative URLs and run UI tests |

---

## 14. Verification Plan

### 14.1 Automated Tests

```bash
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython

# Unit tests
pytest tests/unit/ -v

# Integration tests (mock-based)
pytest tests/integration/ -v -m "not requires_cascor"

# Regression tests
pytest tests/regression/ -v

# Full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### 14.2 New Contract Tests (FIX-K)

#### Metrics shape

```python
def test_metrics_history_contract_matches_demo():
    """Service and demo backends return same metric entry structure."""
    service_entry = service_backend.get_metrics_history(1)[0]
    demo_entry = demo_backend.get_metrics_history(1)[0]
    assert set(service_entry.keys()) == set(demo_entry.keys())
    assert "metrics" in service_entry  # nested, not flat
    assert "network_topology" in service_entry
    assert "loss" in service_entry["metrics"]
```

#### Current metrics snapshot shape

```python
def test_current_metrics_contract_matches_demo():
    """Service current metrics must use same nested format as demo mode."""
    service_entry = service_backend.get_current_metrics()
    assert "metrics" in service_entry
    assert "network_topology" in service_entry
```

#### Topology shape

```python
def test_topology_contract_matches_demo():
    """Service and demo backends return same topology structure."""
    service_topo = service_backend.get_network_topology()
    demo_topo = demo_backend.get_network_topology()
    assert "input_units" in service_topo
    assert isinstance(service_topo["hidden_units"], int)
    assert "connections" in service_topo
    assert set(service_topo.keys()) == set(demo_topo.keys())
```

#### Uppercase status hardening

```python
def test_normalize_status_accepts_uppercase():
    """Status normalization handles uppercase enum names."""
    assert CascorStateSync._normalize_status("STARTED") == "Started"
    assert CascorStateSync._normalize_status("PAUSED") == "Paused"
    assert CascorStateSync._normalize_status("COMPLETED") == "Completed"
    assert CascorStateSync._normalize_status("STOPPED") == "Stopped"
    assert CascorStateSync._normalize_status("FAILED") == "Failed"
```

### 14.3 Manual Integration Test

```bash
# Terminal 1: Start juniper-data
cd /home/pcalnon/Development/python/Juniper/juniper-data
conda activate JuniperData
PYTHON_GIL=0 uvicorn juniper_data.api.app:app --host 0.0.0.0 --port 8100

# Terminal 2: Start juniper-cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
JUNIPER_CASCOR_PORT=8201 python server.py

# Terminal 3: Start juniper-canopy (service mode)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
CASCOR_SERVICE_URL="http://localhost:8201" uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 4: Verify API responses
# Metrics history (P5-RC-01 — should now be nested):
curl -s http://localhost:8050/api/metrics/history?limit=2 | python3 -m json.tool
# Expected: {"history": [{"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, "phase": "...", ...}]}

# Current metrics (P5-RC-09 — should now be nested):
curl -s http://localhost:8050/api/metrics | python3 -m json.tool
# Expected: {"epoch": N, "metrics": {"loss": ..., "accuracy": ...},
#            "network_topology": {"hidden_units": N}, ...}

# Topology (P5-RC-02 — should now be graph-oriented):
curl -s http://localhost:8050/api/network/topology | python3 -m json.tool
# Expected: {"input_units": 2, "output_units": 1, "hidden_units": N,
#            "nodes": [...], "connections": [...]}

# Status (should already work):
curl -s http://localhost:8050/api/status | python3 -m json.tool
# Expected: {"is_running": true, "phase": "output", "current_epoch": N, ...}
```

### 14.4 Visual Verification Checklist

- [ ] Loss chart displays live training data (not flat line at 0)
- [ ] Accuracy chart displays accuracy curve (not flat at 0)
- [ ] Current loss display shows actual value (not "0.0000" or "--")
- [ ] Current accuracy display shows actual percentage (not "0.00%")
- [ ] Hidden units count shows actual count (not always 0)
- [ ] Hidden unit addition markers appear on plots at cascade events
- [ ] Network graph shows input/hidden/output nodes with connections (not empty)
- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Phase indicator shows Output/Candidate transitions (after CasCor fix)
- [ ] Parameter panel shows actual CasCor parameters (not defaults)
- [ ] Parameter changes from Canopy apply to running CasCor
- [ ] Stopping Canopy does not stop CasCor training
- [ ] Restarting Canopy reconnects and shows correct state/metrics
- [ ] Connect to CasCor with training already in progress (non-destructive attach)
- [ ] Dashboard works when served from non-`localhost:8050` deployment path
- [ ] Uppercase status inputs normalize correctly in tests/fakes

---

## 15. Files Requiring Modification

### 15.1 juniper-canopy — Required

| File | Issues Addressed | Changes |
|---|---|---|
| `src/backend/cascor_service_adapter.py` | P5-RC-01, -02, -03, -04, -09, -12, -12b, -13, -14 | Add `_to_dashboard_metric()`, apply in `get_recent_metrics()` and `get_current_metrics()`; add `_transform_topology()`, apply in `extract_network_topology()`; expand relay callback; fix param maps |
| `src/backend/state_sync.py` | P5-RC-03, -07, -10 | Make `_normalize_status()` case-insensitive; normalize synced metrics history; map params to Canopy namespace |
| `src/backend/service_backend.py` | P5-RC-08 | Route sync through adapter/adapter helpers instead of raw client |
| `src/frontend/components/metrics_panel.py` | P5-RC-11 | Replace 6 hardcoded `localhost:8050` URLs with relative paths |
| `src/main.py` | P5-RC-15 | Guard double initialization on fallback path |
| `src/tests/unit/test_response_normalization.py` | P5-RC-16 | Add nested format contract tests; add uppercase status tests; update flat-format assertions |

### 15.2 juniper-cascor — Required (cross-repo)

| File | Issues Addressed | Changes |
|---|---|---|
| `src/api/lifecycle/monitor.py` | P5-RC-06 | Add `set_phase()` method or support `current_phase` updates |
| `src/api/lifecycle/manager.py` | P5-RC-06 | Call `monitor.set_phase()` on phase transitions |

### 15.3 Optional / Recommended Cleanup

| File | Reason |
|---|---|
| `src/backend/protocol.py` | Formalize backend contract with TypedDict/dataclass (P5-RC-18, long-term) |
| `juniper-cascor-client/testing/fake_client.py` or `testing/scenarios.py` | Align fake responses/status values with real CasCor once contract tests exist |

### 15.4 Files NOT Requiring Modification

- `metrics_panel.py` (for P5-RC-01) — fix is in backend, not the panel's access patterns
- `dashboard_manager.py` — callbacks are correct; data they receive is wrong
- `demo_mode.py` — demo format is the target format (working reference)
- `demo_backend.py` — working reference implementation
- `network_visualizer.py` (for P5-RC-02) — fix is in adapter, not the visualizer
- `juniper-cascor-client/` — no changes needed (Phase 1 FIX-SYS already applied)

---

## 16. Post-Synthesis Validation Notes

### 16.1 Code Validation Results

All line numbers and code patterns in this document were independently verified against the current codebase HEAD:

| Validation Area | Result | Notes |
|---|---|---|
| `_normalize_metric()` flat output (lines 431-460) | **CONFIRMED** | Exact match |
| Nested metric access in dashboard (10 locations) | **CONFIRMED** | All line numbers verified |
| `extract_network_topology()` passthrough (lines 480-484) | **CONFIRMED** | Exact match |
| Relay callback forwards status+phase (lines 218-225) | **CONFIRMED** | Also handles `event` type at 228-235 |
| `_normalize_status()` mapping (lines 134-154) | **CONFIRMED** | Off by 1 on method start (134 vs 135) |
| `.lower()` at sync path (line 70) | **CONFIRMED** | Exact match |
| Double initialization (lines 177, 180) | **CONFIRMED** | Exact match |
| 6 hardcoded localhost URLs | **CONFIRMED** | Lines 1000, 1021, 1155, 1187, 1231, 1274 |
| CasCor `current_phase` never updated (line 111) | **CONFIRMED** | Only one assignment in entire codebase |
| Demo mode nested format (lines 1162-1177) | **CONFIRMED** | File lives in `src/demo_mode.py` |
| Raw client passed to state sync (line 189) | **CONFIRMED** | Exact match |

### 16.2 Key Reconciliation Decisions

This final document:

- **Keeps Proposal A's evidence** where it improves precision (title-case CasCor broadcasts)
- **Keeps Proposal B's issue coverage** where it prevents omissions (P5-RC-08, P5-RC-09, P5-RC-10, P5-RC-12b)
- **Follows the directive** where a true latent compatibility bug must be fixed (P5-RC-03)
- **Does not simply choose one proposal** over the other — it synthesizes the strongest findings from both

### 16.3 Completeness Assessment

Given the depth of analysis (7 Phase 3 proposals → 4 Phase 4 proposals → 2 Phase 5 proposals → this final synthesis with code verification), there is high confidence in the completeness of the issue registry. No new issues were discovered during final validation.

---

## Appendix A: Phase 4 Proposal Assessment

### Per-Proposal Summary

| Aspect | P4-A (002192f3) | P4-B (66a019dc) | P4-C (cd8254d3) | P4-D (d7dcbd5a) |
|---|---|---|---|---|
| **Author** | Amp | Claude (Opus 4.6) | Amp | Claude (Opus 4.6) |
| **Issues found** | 13 | 16 | 15 + 1 KL | 19 |
| **False positives** | 2 | 2 | 3 | 3 |
| **Unique contributions** | Clean priority matrix | Upstream relay root cause | Latent severity nuance | ISS-12, ISS-13 state sync gaps |
| **Strengths** | Concise, actionable, explicit retractions | Most comprehensive dependency graph | Strongest self-validation, most honest | Deepest architecture, best evidence inventory |
| **Gaps** | Missed /api/metrics, sync bypass | Missed sync params, dual status | Topology severity underrated, initial URL undercount | Most verbose/granular |
| **Accuracy** | ~95% | ~95% | ~90% | ~95% |

### Underlying Phase 3 Proposal Attribution

Most valuable unique findings traced back to:

| Finding | Phase 3 Source | Unique Contribution |
|---|---|---|
| Topology format mismatch (P5-RC-02) | v2 | Only proposal with complete 6-point structural analysis and transformation code |
| CasCor phase bug (P5-RC-06) | v5 | Only proposal to identify a cross-repo bug |
| Broadest scope (11 issues) | v4 | Identified deployment, parameter, and dataset issues |
| Systemic contract concern (P5-RC-18) | v6, v7 | Elevated individual symptoms to architectural root cause |
| State sync bypass (P5-RC-08) | v7 | Deepest analysis of state sync architectural gaps |

### Phase 5 Proposal Assessment

| Aspect | Proposal A (7f73219c) | Proposal B (8b7d1ee8) |
|---|---|---|
| **Issue count** | 14 active + RC-SYS + KL-1 | 18 active + P5-RC-18 + KL-1 |
| **Most valuable contribution** | Accurate title-case evidence for P5-RC-03 | More complete issue coverage and structural edge cases |
| **Key strength** | Rigorous code-level validation with retraction evidence | Comprehensive numbering and granular separation of issues |
| **Key limitation** | Retracted P5-RC-03 (overcorrected based on current behavior) | Retained issues that Proposal A validly subsumed |

---

## Appendix B: Complete Phase 3 → Phase 5 → Final Issue Lineage

| Final ID | Phase 3 Source(s) | P4-A | P4-B | P4-C | P4-D | Phase 5 A | Phase 5 B | Final |
|---|---|---|---|---|---|---|---|---|
| P5-RC-01 | v1-v7 | ISSUE-1 | P4-RC-01 | RC-1 | ISS-01 | RC-01 | P5-RC-01 | Retained |
| P5-RC-02 | v2, v4 | ISSUE-4 | P4-RC-02 | RC-4 | ISS-04 | RC-02 | P5-RC-02 | Retained |
| P5-RC-03 | v4, v7 | ISSUE-5 | P4-RC-03 | RC-5 | ISS-06 | Retracted | P5-RC-03 | Retained (latent) |
| P5-RC-04 | v1-v7 | ISSUE-2 | P4-RC-05 | RC-2 | ISS-02 | RC-03 | P5-RC-04 | Retained |
| P5-RC-05 | v1-v7 | ISSUE-3 | P4-RC-15 | RC-3 | ISS-03 | RC-12 | P5-RC-05 | Retained |
| P5-RC-06 | v5 | ISSUE-10 | P4-RC-04 | RC-12 | ISS-08 | RC-04 | P5-RC-06 | Retained |
| P5-RC-07 | v1, v3, v5, v6, v7 | ISSUE-6 | P4-RC-06 | RC-6 | ISS-05 | RC-05 | P5-RC-07 | Retained |
| P5-RC-08 | v7 | — | P4-RC-06 (part) | — | ISS-13 | — | P5-RC-08 | Retained |
| P5-RC-09 | v6 | — | P4-RC-09 | (subsumed) | ISS-07 | S | P5-RC-09 | Retained (2nd path) |
| P5-RC-10 | v7 | — | — | — | ISS-12 | — | P5-RC-10 | Retained |
| P5-RC-11 | v4 | ISSUE-7 | P4-RC-07 | RC-7 | ISS-10 | RC-06 | P5-RC-11 | Retained |
| P5-RC-12 | v2, v4 | ISSUE-8 | P4-RC-11 | RC-9 | ISS-15 | RC-09 | P5-RC-12 | Retained |
| P5-RC-12b | v2 | ISSUE-8 | P4-RC-13 | RC-9 (part) | ISS-15b | P | P5-RC-12b | Retained |
| P5-RC-13 | v4 | ISSUE-8 | P4-RC-12 | RC-10 | ISS-16 | RC-10 | P5-RC-13 | Retained |
| P5-RC-14 | v4, v7 | — | P4-RC-10 | RC-8 | ISS-11 | RC-08 | P5-RC-14 | Retained |
| P5-RC-15 | v5, v6 | ISSUE-11 | P4-RC-14 | RC-11 | ISS-18 | RC-11 | P5-RC-15 | Retained |
| P5-RC-16 | v5, v7 | ISSUE-13 | — | RC-13 | ISS-19 | RC-13 | P5-RC-16 | Retained |
| P5-RC-17 | v4 | — | — | RC-14 | ISS-14 | RC-14 | P5-RC-17 | Retained |
| P5-RC-18 | v4, v6, v7 | ISSUE-12 | P4-RC-16 | RC-15 | ISS-17 | RC-SYS | P5-RC-18 | Retained |
| KL-1 | v4 | ISSUE-9 | P4-RC-08 | KL-1 | ISS-09 | P (active) | KL-1 | Known Limitation |

---

## Appendix C: Evidence Inventory

### C.1 Primary Evidence Files

| File | Repository | Issues |
|---|---|---|
| `src/backend/cascor_service_adapter.py` | juniper-canopy | P5-RC-01, -02, -03, -04, -09, -12, -13, -14 |
| `src/backend/service_backend.py` | juniper-canopy | P5-RC-08, KL-1 |
| `src/backend/state_sync.py` | juniper-canopy | P5-RC-03, -07, -10 |
| `src/frontend/components/metrics_panel.py` | juniper-canopy | P5-RC-01, -09, -11 |
| `src/frontend/network_visualizer.py` | juniper-canopy | P5-RC-02 |
| `src/demo_mode.py` | juniper-canopy | P5-RC-01, -02 (reference format) |
| `src/backend/demo_backend.py` | juniper-canopy | P5-RC-02 (reference format) |
| `src/frontend/dashboard_manager.py` | juniper-canopy | P5-RC-05 |
| `src/main.py` | juniper-canopy | P5-RC-15 |
| `src/backend/protocol.py` | juniper-canopy | P5-RC-18 |
| `src/backend/data_adapter.py` | juniper-canopy | P5-RC-18 (dead abstractions) |
| `src/api/lifecycle/manager.py` | juniper-cascor | P5-RC-02, -04, -06 |
| `src/api/lifecycle/monitor.py` | juniper-cascor | P5-RC-06 |
| `src/api/lifecycle/state_machine.py` | juniper-cascor | P5-RC-03 |
| `src/api/models/training.py` | juniper-cascor | P5-RC-12, -13 |
| `testing/fake_client.py` | juniper-cascor-client | P5-RC-03 |
| `testing/scenarios.py` | juniper-cascor-client | P5-RC-02 (third format) |
| `src/tests/unit/test_response_normalization.py` | juniper-canopy | P5-RC-16 |

### C.2 Key Line Numbers (all verified)

| Evidence | File | Line(s) |
|---|---|---|
| `_normalize_metric()` flat output | `cascor_service_adapter.py` | 431-460 |
| `get_current_metrics()` flat path | `cascor_service_adapter.py` | 86-94 |
| Nested metric access in dashboard | `metrics_panel.py` | 1091, 1120-1122, 1330, 1449-1450, 1499, 1561-1562 |
| Demo nested format production | `demo_mode.py` | 1162-1177 |
| Relay callback (status+phase only) | `cascor_service_adapter.py` | 218-225 |
| Relay event handler | `cascor_service_adapter.py` | 228-235 |
| Relay raw metrics broadcast | `cascor_service_adapter.py` | 203-206 |
| WebSocket data div (unused) | `dashboard_manager.py` | 876 |
| Topology passthrough (no transform) | `cascor_service_adapter.py` | 480-484 |
| CasCor topology endpoint | `lifecycle/manager.py` | 563-585 |
| Demo topology format | `demo_backend.py` | 129-169 |
| Topology validation guard | `network_visualizer.py` | 351 |
| `_normalize_status()` mapping | `state_sync.py` | 134-154 |
| Sync path `.lower()` | `state_sync.py` | 70 |
| Relay path (no `.lower()`) | `cascor_service_adapter.py` | 222 |
| CasCor enum `.name` uppercase | `state_machine.py` | 21-28 |
| CasCor WS broadcast title-case | `lifecycle/manager.py` | 111 |
| State sync raw client usage | `service_backend.py` | 189 |
| State sync metrics storage | `state_sync.py` | 115-129 |
| Hardcoded localhost URLs | `metrics_panel.py` | 1000, 1021, 1155, 1187, 1231, 1274 |
| `current_phase` initialization | `monitor.py` | 111 |
| `current_phase` used in metrics | `monitor.py` | 171, 211 |
| Double init in fallback | `main.py` | 177, 180 |
| Decision boundary transform (reference) | `cascor_service_adapter.py` | 495-543 |
| CasCor runtime PATCH updatable keys | `manager.py` | 545-553 |
| `TrainingParamUpdateRequest` fields | `api/models/training.py` | 45-54 |
| FakeCascorClient topology shape | `testing/scenarios.py` | 248-257 |
| `BackendProtocol` returns | `protocol.py` | 59-140 |

---

## Appendix D: Document Lineage

```text
Phase 0 (Original Analysis):
  1_CANOPY_EXTERNAL_CASCOR_PLAN.md
  2_INVESTIGATION_PLAN_EXTERNAL_CASCOR_METRICS_DISPLAY.md
  3_ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md
  4_CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md

Phase 1 (Development Plans — Implemented):
  5a_EXTERNAL_CASCOR_INTEGRATION_DEV_PLAN.md
  5b_DEVELOPMENT_PLAN_EXTERNAL_CASCOR_FIX.md

Phase 2 (Root Cause Analysis — Implemented):
  PHASE_2_MERGED_EXTERNAL_CASCOR_DEV_PLAN_v1.md
  PHASE_2_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_DISPLAY_v3.md
  PHASE_2_UNIFIED_EXTERNAL_CASCOR_DEVELOPMENT_PLAN_v2.md

Phase 3 (7 Independent Proposals):
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v1.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v2.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v3.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v4.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v5.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v6.md
  PHASE_3_ROOT_CAUSE_ANALYSIS_EXTERNAL_CASCOR_v7.md

Phase 4 (4 Independent Comprehensive Analyses):
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_002192f3-fbde-444b-ac3f-2c0e6ceb8f96.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_66a019dc-94ba-47fb-8042-7ce8f974d071.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_cd8254d3-16bb-4212-b551-d9e911afd690.md
  PHASE_4_CANOPY_CASCOR_CONNECTION_ANALYSIS_d7dcbd5a-667d-48ba-8d3a-f11893105c6a.md

Phase 5 (2 Finalist Syntheses):
  PHASE_5_CANOPY_CASCOR_CONNECTION_ANALYSIS_7f73219c-1557-4135-ab44-ef053d4c4097.md
  PHASE_5_CANOPY_CASCOR_CONNECTION_ANALYSIS_8b7d1ee8-a24d-4e2a-bfd6-8df44d7ed326.md

Final Synthesis (This Document):
  FINAL_CANOPY_CASCOR_CONNECTION_ANALYSIS.md
```

---

*End of Final Canopy–CasCor Connection Analysis*
