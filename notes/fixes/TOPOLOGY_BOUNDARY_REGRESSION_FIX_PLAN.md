# Network Topology & Decision Boundary Regression Fix Plan

**Date**: 2026-03-16
**Root Cause**: Data structure key name mismatches in `DemoBackend` methods

---

## Symptoms

| # | Symptom | Tab |
|---|---------|-----|
| S1 | Network topology shows "No network topology available" with all counters at 0 | Network Topology |
| S2 | Decision boundary shows "No boundary data available" | Decision Boundaries |

Both occur while training is actively running (e.g., Epoch 359, Hidden Units 11).

---

## Root Cause Analysis

### RC-1: Topology Key Name Mismatch

**File**: `src/backend/demo_backend.py` lines 162-168

`DemoBackend.get_network_topology()` returns:
```python
{"nodes": [...], "connections": [...], "input_size": 2, "output_size": 2, "hidden_units": 11}
```

**File**: `src/frontend/components/network_visualizer.py` line 351

`NetworkVisualizer` checks:
```python
if not topology_data or topology_data.get("input_units", 0) == 0:
    # Shows empty graph
```

Since the key is `input_size` (not `input_units`), `.get("input_units", 0)` returns the default `0`, triggering the empty graph. The counter extraction at lines 410-412 also uses `input_units`/`output_units`.

### RC-2: Decision Boundary Key Name AND Data Shape Mismatch

**File**: `src/backend/demo_backend.py` lines 223-232

`DemoBackend.get_decision_boundary()` returns:
```python
{"x": [1D linspace], "y": [1D linspace], "z": [[2D grid]], ...}
```

**File**: `src/frontend/components/decision_boundary.py` lines 291-296

`DecisionBoundary._create_boundary_plot()` expects:
```python
xx = np.array(boundary_data.get("xx", []))  # 2D meshgrid
yy = np.array(boundary_data.get("yy", []))  # 2D meshgrid
Z = np.array(boundary_data.get("Z", []))    # uppercase Z
```

And at lines 303-304:
```python
x=xx[0],       # First row of 2D meshgrid
y=yy[:, 0],   # First column of 2D meshgrid
```

The mismatches are:
1. Key names: `x`/`y`/`z` vs `xx`/`yy`/`Z`
2. Data shape: Backend returns 1D linspace for x/y; frontend expects 2D meshgrid

---

## Fix

### Fix 1: Topology keys in `demo_backend.py`

Change `input_size` → `input_units` and `output_size` → `output_units` in the return dict.

### Fix 2: Decision boundary keys and shapes in `demo_backend.py`

1. Change key names: `x` → `xx`, `y` → `yy`, `z` → `Z`
2. Return 2D meshgrid arrays (`grid_x`, `grid_y`) instead of 1D linspace arrays

---

## Files Modified

| File | Change |
|------|--------|
| `src/backend/demo_backend.py` | Fix topology return keys and boundary return keys/shapes |
| `src/tests/regression/test_topology_boundary_data_contract.py` | New regression test |
